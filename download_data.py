"""Fetch reference iOS data directly from the official CDN, without a game login."""
import argparse
import base64
import hashlib
import json
import re
import time
import zlib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlsplit

import brotli
import requests
from urllib3.exceptions import HTTPError as TransportError

BASE = 'https://assets-e.wds-stellarium.com'
VERSION = '1.96.0'
MANIFEST = {'uri': '2026-09-22/mastermemory_1790021136_1790021136.db',
            'version': '1790021136_1790021136', 'publish_timestamp': 1790021136, 'sas_token': ''}
MASTER_HASH = '877132d235066a563f1b612761d299c7922f5050f0dbe6533b929e59b36edda8'
CATALOG_HASHES = {
    '2d-assets': '8e8a4fd43f8ba3d05ec690cd11fe8026528516dc02c9e0f6224dacf08f69649d',
    '3d-assets': 'dd45682b0753da800ce4b8c0032b44a32786c2a13e0dd92ebdfb4760c04cd531',
    'cri-assets': '821c2c382a5dab12688cf9e99271eb1443903255c5abf9b1f134dd0efa7cdfe2',
}


def safe_path(value):
    if not value or any(p in ('', '.', '..') for p in value.split('/')):
        raise ValueError('Invalid download path')
    if not re.fullmatch(r'[A-Za-z0-9_./()-]+', value):
        raise ValueError('Unexpected download path characters')
    return value


def digest(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def fetch(url, dest, expected=None):
    """Restart at file boundaries; only checksum-verified files are skipped."""
    parts = urlsplit(url)
    if parts.scheme != 'https' or parts.netloc != 'assets-e.wds-stellarium.com' or parts.query or parts.fragment:
        raise ValueError('Only direct official CDN URLs are accepted')
    safe_path(parts.path.lstrip('/'))
    dest = Path(dest)
    receipt = dest.with_name(dest.name + '.sha256')
    known = expected or (receipt.read_text().strip() if receipt.exists() else None)
    if dest.is_file() and known and digest(dest) == known:
        return {'status': 'verified-existing', 'bytes': dest.stat().st_size, 'sha256': known}
    dest.parent.mkdir(parents=True, exist_ok=True)
    temp = dest.with_name(dest.name + '.part')
    for attempt in range(3):
        try:
            with requests.get(url, stream=True, timeout=(15, 90), allow_redirects=False,
                              headers={'Accept-Encoding': 'identity'}) as response:
                if response.status_code != 200:
                    if response.status_code >= 500 or response.status_code == 429:
                        raise requests.RequestException(f'HTTP {response.status_code}')
                    return {'status': f'HTTP {response.status_code}'}
                if 'text/' in response.headers.get('Content-Type', ''):
                    raise ValueError('Unexpected text response')
                encoding = response.headers.get('Content-Encoding', '').lower()
                if encoding not in ('', 'identity', 'gzip', 'deflate', 'br'):
                    raise ValueError('Unsupported content encoding')
                decoder = (brotli.Decompressor() if encoding == 'br' else
                           zlib.decompressobj(16 + zlib.MAX_WBITS if encoding == 'gzip' else zlib.MAX_WBITS)
                           if encoding in ('gzip', 'deflate') else None)
                sha, md5, size, wire_size = hashlib.sha256(), hashlib.md5(), 0, 0
                with temp.open('wb') as out:
                    for chunk in response.raw.stream(1024 * 1024, decode_content=False):
                        md5.update(chunk); wire_size += len(chunk)
                        decoded = (decoder.process(chunk) if encoding == 'br' else decoder.decompress(chunk)) if decoder else chunk
                        out.write(decoded); sha.update(decoded); size += len(decoded)
                    if decoder and encoding != 'br':
                        tail = decoder.flush(); out.write(tail); sha.update(tail); size += len(tail)
                    if decoder and not (decoder.is_finished() if encoding == 'br' else decoder.eof):
                        raise ValueError('Incomplete compressed download')
                length = response.headers.get('Content-Length')
                if not size or (length and wire_size != int(length)):
                    raise ValueError('Incomplete download')
                if response.headers.get('Content-MD5') and base64.b64encode(md5.digest()).decode() != response.headers['Content-MD5']:
                    raise ValueError('Content-MD5 mismatch')
                if expected and sha.hexdigest() != expected:
                    raise ValueError('Pinned SHA256 mismatch')
                temp.replace(dest)
                receipt.write_text(sha.hexdigest())
                return {'status': 'downloaded', 'bytes': size, 'sha256': sha.hexdigest()}
        except (requests.RequestException, TransportError, ValueError, zlib.error, brotli.error) as exc:
            if attempt == 2:
                return {'status': 'failed', 'error': str(exc)}
            time.sleep(2 ** attempt)
        finally:
            temp.unlink(missing_ok=True)


def bundle_paths(catalog, kind):
    paths = set()
    for internal in catalog['m_InternalIds']:
        if not internal.endswith('.bundle'):
            continue
        match = re.match(r'^(\d+)#(.*)$', internal)
        resolved = catalog['m_InternalIdPrefixes'][int(match[1])] + match[2] if match else internal
        prefix = f'http://{kind}/iOS/'
        if not resolved.startswith(prefix):
            raise ValueError('Unexpected catalog bundle prefix: ' + resolved)
        paths.add(safe_path(resolved[len(prefix):]))
    return sorted(paths)


def metadata_jobs(raw):
    # Decode with the same pinned MasterMemory implementation as the server.
    from helpers.mastermemory import unpack
    from models.keys import KEYS
    tables = unpack(raw)
    def table(name):
        # Only scalar identifiers are needed; avoid helpers.msgpack, which loads
        # config.yml before a first-time installation has generated it.
        return [{('id' if field == 'id_' else field): row[key]
                 for key, field, *_ in KEYS[name] if key < len(row)}
                for row in tables[name]]
    charts = {(str(r['music_master_id']), f"{r['difficulty']}.enc") for r in table('LiveMaster')}
    charts.update((str(r['id']), 'music_config.enc') for r in table('MusicMaster'))
    for row in table('AnotherNotationMaster'):
        folder = str(row['notation_path'])
        if not folder.isdigit():
            raise ValueError('Unexpected notation folder')
        charts.add((folder, f"{row['difficulty']}.enc")); charts.add((folder, 'music_config.enc'))
    jobs = [('assets/Notations/' + safe_path(f'{folder}/{name}'),
             BASE + '/production/Notations/' + safe_path(f'{folder}/{name}')) for folder, name in sorted(charts)]
    comics = set()
    for group in tables['ComicMaster']:
        for episode in group[2] or []:
            for element in json.loads(episode[3] or '[]'):
                if element.get('Element') == 6:
                    comics.add(safe_path(element['Data'] + '.png'))
    for name in sorted(comics):
        rel = 'production/static-assets/Resources/Textures/Comic/' + name
        jobs.append(('static-assets/' + rel, BASE + '/' + rel))
    return jobs


def story_supplement():
    source = Path(__file__).resolve().parent / 'story-supplement.json'
    entries = json.loads(source.read_text(encoding='utf-8'))['episodes']
    for eid, entry in entries.items():
        if not eid.isdigit():
            raise ValueError('Invalid episode ID')
        name = entry['metadata']['episode_detail_asset_source']
        if not re.fullmatch(r'scenes/' + re.escape(eid) + r'_[a-f0-9]+\.bin', name):
            raise ValueError('Invalid story scene identifier')
        if not re.fullmatch(r'[a-f0-9]{64}', entry['sha256']):
            raise ValueError('Invalid story checksum')
        if entry['metadata']['story_type'] not in (1, 3):
            raise ValueError('Unexpected supplemental story type')
    return entries


def save_story_manifest(output, entries):
    # Publish metadata only for verified scene files. Keep unrelated local entries.
    path = output / 'episode-manifest.json'
    manifest = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    for eid, entry in entries.items():
        scene = output / entry['metadata']['episode_detail_asset_source']
        if scene.is_file() and digest(scene) == entry['sha256']:
            manifest[eid] = entry['metadata']
    if manifest:
        temp = path.with_suffix('.tmp')
        temp.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
        temp.replace(path)


def run(output, workers=4, limit=0, metadata_only=False):
    from server import bootstrap
    bootstrap()
    output = Path(output).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    def required(url, path, checksum):
        result = fetch(url, output / path, checksum)
        if result['status'] not in ('downloaded', 'verified-existing'):
            raise RuntimeError(f'{path}: {result}')
    required(BASE + '/master-data/production/' + MANIFEST['uri'], 'master-original.db', MASTER_HASH)
    (output / 'master-manifest.json').write_text(json.dumps(MANIFEST, indent=2))
    jobs = []
    for kind, checksum in CATALOG_HASHES.items():
        rel = f'catalogs/{kind}.json.br'
        required(f'{BASE}/production/{kind}/iOS/{VERSION}/catalog_{VERSION}.json.br', rel, checksum)
        catalog = json.loads(brotli.decompress((output / rel).read_bytes()))
        dest = output / f'assets/{kind}/ios/catalog.json'
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(catalog))
        jobs.extend((f'assets/{kind}/ios/{p}', f'{BASE}/production/{kind}/iOS/{VERSION}/{p}')
                    for p in bundle_paths(catalog, kind))
    jobs.extend(metadata_jobs((output / 'master-original.db').read_bytes()))
    stories = story_supplement()
    expected = {}
    for entry in stories.values():
        path = entry['metadata']['episode_detail_asset_source']
        expected[path] = entry['sha256']
        jobs.append((path, BASE + '/master-data/production/' + path))
    print(f'Enumerated {len(jobs)} media files for iOS {VERSION}.', flush=True)
    (output / 'download-plan.json').write_text(json.dumps(jobs))
    if metadata_only:
        print('Metadata only: media has NOT been downloaded.'); return 0
    selected = jobs[:limit] if limit else jobs
    errors = 0
    report = output / 'download-report.jsonl'
    def work(job):
        path, url = job
        return {'path': path, **fetch(url, output / path, expected.get(path))}
    with report.open('w') as log, ThreadPoolExecutor(max_workers=workers) as pool:
        for n, result in enumerate(pool.map(work, selected), 1):
            errors += result['status'] not in ('downloaded', 'verified-existing')
            log.write(json.dumps(result) + '\n'); log.flush()
            if n % 100 == 0 or n == len(selected):
                print(f'{n}/{len(selected)} processed; missing/failed={errors}', flush=True)
    save_story_manifest(output, stories)
    print(f'Report: {report}. Rerun to retry missing files; verified files are skipped.')
    if limit: print('LIMITED TEST: this is not a complete media download.')
    return 2 if errors else 0


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', default='data')
    p.add_argument('--workers', type=int, choices=range(1, 9), default=4)
    p.add_argument('--limit', type=int, default=0, help='Download only N media files (test only)')
    p.add_argument('--metadata-only', action='store_true', help='Fetch master/catalogs and enumerate media')
    args = p.parse_args()
    if args.limit < 0: p.error('--limit must be nonnegative')
    raise SystemExit(run(args.output, args.workers, args.limit, args.metadata_only))

if __name__ == '__main__':
    main()
