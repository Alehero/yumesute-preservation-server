"""Recoverable installation, data repair, database startup and private backups."""
import asyncio
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import zipfile


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, indent=2), encoding='utf-8')
    temp.chmod(0o600)
    temp.replace(path)


@contextmanager
def installation_lock(root):
    """OS locks release automatically on exit/crash, including on Windows."""
    path = root / 'private/operation.lock'
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a+b') as handle:
        handle.seek(0); handle.write(b'0'); handle.flush(); handle.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise RuntimeError('Another server/setup/backup command is running in this folder. Stop it first.') from None
        try:
            yield
        finally:
            if os.name == 'nt':
                handle.seek(0); msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle, fcntl.LOCK_UN)


def configuration(root):
    import yaml
    path = root / 'vendor/server-of-dreams/config.yml'
    if not path.is_file():
        raise RuntimeError('Setup incomplete. Run: uv run --locked python server.py setup')
    return yaml.safe_load(path.read_text())


def managed_database(root, db):
    env = root / '.env'
    values = dict(line.split('=', 1) for line in env.read_text().splitlines() if '=' in line) if env.exists() else {}
    return (db['host'] in ('localhost', '127.0.0.1') and db['database'] == 'yumesute'
            and db['username'] == 'yumesute' and str(db['port']) == values.get('POSTGRES_PORT', '55433')
            and db['password'] == values.get('POSTGRES_PASSWORD'))


def database_ready(db):
    import asyncpg
    async def probe():
        conn = await asyncpg.connect(host=db['host'], port=db['port'], user=db['username'],
                                     password=db['password'], database=db['database'], timeout=5)
        try:
            await conn.fetchval('SELECT 1')
        finally:
            await conn.close()
    try:
        asyncio.run(probe())
        return True
    except (OSError, TimeoutError):
        return False
    except asyncpg.PostgresError:
        raise RuntimeError('PostgreSQL responded but rejected the configured login/database. Check configuration; do not delete its volume.') from None


def ensure_database(root, no_docker=False):
    db = configuration(root)['database']
    if database_ready(db):
        print('Database ready (existing service).', flush=True)
        return
    if no_docker or not managed_database(root, db):
        raise RuntimeError('Configured PostgreSQL is unavailable. Start your PostgreSQL service and retry; no database was reset.')
    if not shutil.which('docker'):
        raise RuntimeError('Docker is not installed. Install and open Docker Desktop, then retry start/setup.')
    print('Starting the installation database with Docker Compose…', flush=True)
    result = subprocess.run(['docker', 'compose', 'up', '-d', '--wait', '--wait-timeout', '120', 'db'], cwd=root)
    if result.returncode:
        raise RuntimeError('Database startup failed. Open Docker Desktop and inspect docker compose ps/logs db, then retry. Existing data was retained.')
    if not database_ready(db):
        raise RuntimeError('Database container started but the configured connection is unavailable. Check ports and configuration.')


def require_stopped(root):
    # Also catches servers started before operation locking was introduced.
    state = root / 'private/start-options.json'
    port = json.loads(state.read_text()).get('port', 8125) if state.exists() else 8125
    try:
        with socket.create_connection(('127.0.0.1', port), timeout=.3):
            pass
    except OSError:
        return
    raise RuntimeError(f'Port {port} is active. Stop the game server before setup, repair or backup (keep PostgreSQL running).')


def download(source, allow_missing, platform="ios"):
    import download_data
    result = download_data.run(source, platform=platform)
    if result and not allow_missing:
        raise RuntimeError('Some downloads failed. Inspect data-dir/download-report.jsonl and retry the same command. Use --allow-missing only to accept incomplete media explicitly.')
    return result


def setup(root, args, server):
    require_stopped(root)
    if (root / 'private/account.json').exists():
        print('Existing account found: skipping downloads and preparation. Use repair-data for missing media.', flush=True)
    else:
        config_file = root / 'vendor/server-of-dreams/config.yml'
        external = config_file.exists() and not managed_database(root, configuration(root)['database'])
        if not args.no_docker and not external:
            if not shutil.which('docker'):
                raise RuntimeError('Install and open Docker Desktop before setup (or use --no-docker with your PostgreSQL service).')
            if subprocess.run(['docker','info'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode:
                raise RuntimeError('Docker is unavailable. Open Docker Desktop before downloading data, then retry setup.')
        if not shutil.which('git'):
            raise RuntimeError('Install Git before running setup.')
        source = Path(args.data_dir).expanduser().resolve()
        if not args.skip_download:
            source.mkdir(parents=True, exist_ok=True)
            if not (source/'master-original.db').exists() and shutil.disk_usage(source).free < 45*1024**3:
                raise RuntimeError('Allow approximately 45 GB free for the first download and installed copy. Free space and retry.')
            print('Checking/downloading game files; verified completed files are reused.', flush=True)
            download(source, args.allow_missing, getattr(args, "platform", "ios"))
        elif not all((source / n).is_file() for n in ('master-original.db', 'master-manifest.json')):
            raise RuntimeError('--skip-download requires an existing game-data folder with its master and manifest.')
        print('Preparing data. Interrupted preparation can be retried before account creation.', flush=True)
        server.prepare(args)
    # start checks the DB and existing state; it never reimports an account.
    server.start(args)


def media_destination(root, relative):
    from download_data import safe_path
    safe_path(relative)
    if relative.startswith('assets/'):
        return root / 'vendor/server-of-dreams/_data' / relative
    if relative.startswith('static-assets/'):
        return root / 'private' / relative
    if relative.startswith('scenes/') or relative == 'help.bin':
        return root / 'private/upstream' / relative
    raise ValueError('Not an installable media path: ' + relative)


def atomic_copy(source, dest, expected):
    from download_data import digest
    if dest.is_file() and digest(dest) == expected:
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    temp = dest.with_name(dest.name + '.repairing')
    try:
        shutil.copyfile(source, temp)
        if digest(temp) != expected:
            raise ValueError('Source changed while copying: ' + str(source))
        temp.replace(dest)
    finally:
        temp.unlink(missing_ok=True)
    return True


def install_verified_media(root, source, platform="ios"):
    """Only downloader-verified media; account/config/master tables are never replaced."""
    import download_data as d
    from supplemental_resources import resources
    pinned = {p: e['sha256'] for p, e in resources().items()}
    stories = d.story_supplement()
    pinned.update({e['metadata']['episode_detail_asset_source']: e['sha256'] for e in stories.values()})
    selected = []
    seen = set()
    for line in (source / 'download-report.jsonl').read_text().splitlines():
        row = json.loads(line)
        if row['status'] not in ('downloaded', 'verified-existing'):
            continue
        rel = row['path']; dest = media_destination(root, rel)
        if rel in seen:
            raise ValueError('Duplicate report entry: ' + rel)
        seen.add(rel)
        src = source / rel; expected = pinned.get(rel, row['sha256'])
        if src.is_symlink() or not src.resolve().is_relative_to(source.resolve()) or d.digest(src) != expected:
            raise ValueError('Invalid repair source: ' + rel)
        if not dest.resolve().is_relative_to(root.resolve()):
            raise ValueError('Repair destination escapes installation: ' + rel)
        selected.append((src, dest, expected))
    # Reconstruct and verify catalogs rather than trusting unverified decoded copies.
    import brotli
    catalogs = []
    for target in d.platforms(platform):
        for kind, expected in d.catalog_hashes(target).items():
            src = source / d.catalog_path(kind, target)
            if d.digest(src) != expected:
                raise ValueError('Invalid catalog: ' + target + '/' + kind)
            catalog = json.loads(brotli.decompress(src.read_bytes()))
            d.bundle_paths(catalog, kind, target)  # Reject mismatched-platform catalogs.
            catalogs.append((root / f'vendor/server-of-dreams/_data/assets/{kind}/{target.lower()}/catalog.json', catalog))
    count = sum(atomic_copy(*item) for item in selected)
    for dest, content in catalogs:
        atomic_json(dest, content)
    # Merge only verified supplemental story metadata; preserve unrelated metadata.
    dest = root / 'private/upstream/episode-manifest.json'
    manifest = json.loads(dest.read_text()) if dest.exists() else {}
    for eid, entry in stories.items():
        rel = entry['metadata']['episode_detail_asset_source']
        if rel in seen:
            manifest[eid] = entry['metadata']
    if manifest:
        atomic_json(dest, manifest)
    return count


def repair(root, args):
    require_stopped(root)
    configuration(root)
    if not (root / 'private/upstream/master-original.db').is_file():
        raise RuntimeError('Preparation incomplete: run setup first.')
    source = Path(args.data_dir).expanduser().resolve()
    # Repair is for this pinned master, never an implicit data-version migration.
    import download_data as d
    if d.digest(root / 'private/upstream/master-original.db') != d.MASTER_HASH:
        raise RuntimeError('Installed master differs from the reference. Refusing automatic repair across data versions.')
    download(source, args.allow_missing, getattr(args, "platform", "ios"))
    result = any(json.loads(line)['status'] not in ('downloaded','verified-existing') for line in (source/'download-report.jsonl').read_text().splitlines())
    count = install_verified_media(root, source, getattr(args, "platform", "ios"))
    print(f'Repaired {count} media files; accounts/configuration unchanged. Restart with server.py start.', flush=True)
    if result:
        print('INCOMPLETE: accepted missing downloads remain listed in download-report.jsonl.', flush=True)


def backup(root, args):
    require_stopped(root)
    db = configuration(root)['database']
    if not database_ready(db):
        raise RuntimeError('Start PostgreSQL before backup, leaving the game server stopped.')
    output = Path(args.output).expanduser().resolve()
    if output.exists():
        raise RuntimeError('Backup destination already exists. Choose a new filename.')
    if output.suffix.lower() != '.zip':
        raise ValueError('Use a .zip backup filename.')
    output.parent.mkdir(parents=True, exist_ok=True)
    ignored = {'.venv', '__pycache__', '.ruff_cache'}
    entries = []
    for base, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = [n for n in dirs if n not in ignored and not (Path(base)==root and n in ('.git','data','logs','backups'))]
        if any((Path(base)/n).is_symlink() for n in dirs):
            raise RuntimeError('Backup found a linked directory. Copy its contents into the installation before backing up: '+str(base))
        for name in files:
            src = Path(base)/name; rel = src.relative_to(root)
            if src.is_symlink():
                raise RuntimeError('Backup found a linked file; copy it locally first: '+str(src))
            if src.resolve() == output or name.endswith(('.pyc', '.part', '.repairing')) or (Path(base)==root and name.endswith(('.zip','.dump'))) or name == 'operation.lock':
                continue
            entries.append((src, rel.as_posix()))
    ca_settings = root / 'private/certificate-store.json'
    if ca_settings.exists():
        selected = json.loads(ca_settings.read_text()).get('ca_dir')
        ca = Path(selected).expanduser().resolve() if selected else root/'private/mitmproxy'
        if not (ca/'mitmproxy-ca.pem').is_file():
            raise RuntimeError('Configured certificate store is missing; backup would be incomplete.')
        if not ca.is_relative_to(root.resolve()):
            for src in ca.rglob('*'):
                if src.is_symlink():
                    raise RuntimeError('External certificate store contains a linked file; copy it locally first.')
                if src.is_file():
                    entries.append((src, 'private/backup-ca/'+src.relative_to(ca).as_posix()))
    estimate = sum(src.stat().st_size for src, _ in entries)
    if shutil.disk_usage(output.parent).free < estimate + 512 * 1024**2:
        raise RuntimeError('Insufficient backup space: allow room for installed files plus a database dump.')
    with tempfile.TemporaryDirectory(prefix='.yumesute-backup-', dir=output.parent) as tempdir:
        temp = Path(tempdir); dump = temp / 'database.dump'
        env = dict(os.environ, PGPASSWORD=str(db['password']))
        if shutil.which('pg_dump'):
            command = ['pg_dump', '-h', str(db['host']), '-p', str(db['port']), '-U', str(db['username']), '-d', str(db['database']), '-Fc']
        elif managed_database(root, db) and shutil.which('docker'):
            command = ['docker', 'compose', 'exec', '-T', 'db', 'pg_dump', '-U', 'yumesute', '-d', 'yumesute', '-Fc']
        else:
            raise RuntimeError('Install PostgreSQL client tools (pg_dump), or use the running Compose database.')
        print('Saving database and installed files. Keep other writers stopped.', flush=True)
        with dump.open('wb') as stream:
            subprocess.run(command, cwd=root, env=env, stdout=stream, check=True)
        with dump.open('rb') as stream:
            valid_dump = stream.read(5) == b'PGDMP'
        if not valid_dump:
            raise RuntimeError('Database dump is not a PostgreSQL custom-format archive.')
        archive = temp / 'backup.zip'; hashes = {}
        from download_data import digest
        with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_STORED, allowZip64=True) as z:
            for src, rel in [(dump, 'database.dump')] + [(src, 'installation/'+rel) for src, rel in entries]:
                before = digest(src); z.write(src, rel)
                if digest(src) != before:
                    raise RuntimeError('File changed during backup: ' + rel)
                hashes[rel] = before
            z.writestr('backup-manifest.json', json.dumps({'format_version':1, 'created_at':time.time(), 'sha256':hashes}, indent=2))
        with zipfile.ZipFile(archive) as z:
            for rel, expected in hashes.items():
                with z.open(rel) as stream:
                    if hashlib.file_digest(stream, 'sha256').hexdigest() != expected:
                        raise RuntimeError('Backup verification failed: ' + rel)
        archive.chmod(0o600)
        archive.replace(output)
    print(f'Verified private backup: {output}. Includes installed assets; excludes duplicate downloads, logs and software environments. Keep it private.')
