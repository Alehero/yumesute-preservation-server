"""Explicit, local-only setup and account management for the release."""
import argparse, asyncio, hashlib, json, os, secrets, shutil, string, subprocess, sys, time, zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent
VENDOR=ROOT/'vendor/server-of-dreams'
PRIVATE=ROOT/'private'
PIN=json.loads((ROOT/'upstream-versions.json').read_text())['server-of-dreams']

def write(path, value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(value,encoding='utf-8');path.chmod(0o600)

def bootstrap():
    if not VENDOR.exists():
        VENDOR.parent.mkdir(exist_ok=True)
        subprocess.run(['git','clone','https://github.com/UnknownSekai/server-of-dreams.git',str(VENDOR)],check=True)
        subprocess.run(['git','-C',str(VENDOR),'checkout','--detach',PIN],check=True)
    actual=subprocess.check_output(['git','-C',str(VENDOR),'rev-parse','HEAD'],text=True).strip()
    if actual!=PIN: raise RuntimeError('Unexpected upstream revision; use a clean release folder')
    sys.path.insert(0,str(VENDOR));sys.path.insert(0,str(ROOT/'tools'))

def prepare(a):
    bootstrap()
    import yaml
    source=Path(a.data_dir).expanduser().resolve()
    required=['master-original.db','master-manifest.json']
    if not all((source/n).is_file() for n in required): raise RuntimeError('Data folder needs master-original.db and master-manifest.json; see DATA.md')
    if (PRIVATE/'account.json').exists(): raise RuntimeError('Account already configured; refusing to replace its data/configuration')
    if not (VENDOR/'config.yml').exists():
        config=yaml.safe_load((VENDOR/'config.example.yml').read_text())
        password=secrets.token_hex(24)
        config.update(server_version='2.31.3',asset_version='1.96.0',local_assets=True,host='127.0.0.1',port=8125,
                      api_endpoint='https://lb-api.wds-stellarium.com',jwt_secret=secrets.token_hex(32))
        config['database'].update(host='127.0.0.1',port=55433,database='yumesute',username='yumesute',password=password)
        write(VENDOR/'config.yml',yaml.safe_dump(config))
        write(ROOT/'.env','POSTGRES_PASSWORD='+password+'\nPOSTGRES_PORT=55433\n')
    dest=PRIVATE/'upstream';dest.mkdir(parents=True,exist_ok=True)
    for name in required+['episode-manifest.json']:
        if (source/name).exists():shutil.copy2(source/name,dest/name)
    for src,dst in [(source/'assets',VENDOR/'_data/assets'),(source/'episodes',VENDOR/'_data/episodes'),(source/'scenes',dest/'scenes'),(source/'static-assets',PRIVATE/'static-assets')]:
        if src.is_dir():shutil.copytree(src,dst,dirs_exist_ok=True)
    from helpers.mastermemory import unpack
    from helpers.msgpack import from_array
    from models.master_data import TABLES
    tables=unpack((dest/'master-original.db').read_bytes())
    output=VENDOR/'_data/masterdata';output.mkdir(parents=True,exist_ok=True)
    for name, rows in tables.items():
        if name in TABLES:
            decoded=[from_array(TABLES[name].__name__,r).model_dump(mode='json',by_alias=True) for r in rows]
            (output/(name+'.json')).write_text(json.dumps(decoded,ensure_ascii=False),encoding='utf-8')
    print('Prepared pinned backend and local master data. Start PostgreSQL, then import-account or fresh-account.')
    print('Missing optional media is not downloaded automatically. Run doctor to inspect local coverage.')

def fresh_song_tickets():
    value=json.loads((ROOT/'preservation-rules.json').read_text()).get('fresh_song_tickets',10000)
    if type(value) is not int or not 0 <= value <= 1000000:
        raise ValueError('fresh_song_tickets must be an integer between 0 and 1000000')
    return value


def schema():
    bootstrap()
    subprocess.run([sys.executable,'-m','scripts.database_setup','--config',str(VENDOR/'config.yml')],cwd=VENDOR,check=True,stdout=subprocess.DEVNULL)

def transfer_config(uid,mode,bridge=None):
    password=''.join(secrets.choice(string.ascii_letters+string.digits) for _ in range(16))
    salt=secrets.token_hex(16);code=''.join(secrets.choice(string.digits) for _ in range(10))
    state={'user_id':uid,'mode':mode,'transfer':{'code':code,'salt':salt,'hash':hashlib.scrypt(password.encode(),salt=salt.encode(),n=16384,r=8,p=1).hex()}}
    if bridge: state['token_sha256']=bridge['token_sha256']
    return state,f'Local server only / ローカルサーバー専用\nLinking ID / 連携ID: {code}\nPassword / 連携パスワード: {password}\n'

async def account(a):
    if (PRIVATE/'account.json').exists(): raise RuntimeError('This installation already has an account. Import refuses to overwrite it.')
    raw=None;bridge=None;rows=[]
    starter_tickets=fresh_song_tickets() if a.command=='fresh-account' else 0
    if a.command=='import-account':
        from exporter import verify_export
        verify_export(a.archive)
        with zipfile.ZipFile(a.archive) as z:
            raw=z.read('user-data.response.bin')
            if 'account-bridge.json' in z.namelist():bridge=json.loads(z.read('account-bridge.json'))
    schema()
    from helpers.config import database
    from core import YumeApp
    from helpers.cache import load_master_data
    from helpers.user_data import user_data,_table
    from helpers.mastermemory import to_json
    from helpers.auth import _new_user_id
    from helpers.user_hash import hash_id
    from db.account import create_account,add_hash_user_id
    from db.defaults import create_default_user_data
    from db import user as queries
    from models.unions import IDATA_OBJECT
    from import_account import row_dict
    from protocol import envelope
    load_master_data()
    if raw:
        original=envelope(raw)[1]
        for item in original:
            if item is None:continue
            tag,values=item
            name=IDATA_OBJECT.get(tag)
            if name is None:raise RuntimeError(f'Unsupported account entity {tag}; original ZIP remains intact')
            rows.append((name,row_dict(name,values)))
        uid=next(r['id'] for name,r in rows if name=='User')
    app=YumeApp(config=database);await app.yume_setup()
    # Files are staged before commit; account.json is the completion marker.
    # A failure never overwrites an existing account; a DB-only partial setup is
    # detected on retry rather than silently reset.
    try:
        async with app.acquire_db() as conn,conn.transaction():
            await conn.conn.execute('LOCK TABLE accounts IN EXCLUSIVE MODE')
            if await conn.conn.fetchval('SELECT count(*) FROM accounts'):raise RuntimeError('Database is not empty; refusing to overwrite progress')
            if raw is None:uid=await _new_user_id(conn)
            await conn.execute(create_account(uid,secrets.token_urlsafe(32),'AppStore',int(time.time()),int(time.time())))
            if raw:
                for name,row in rows:
                    fn=getattr(queries,'upsert_'+_table(name),None)
                    if fn is None:raise RuntimeError('Unsupported account table '+name)
                    await conn.execute(fn(uid,row))
                user=next(r for n,r in rows if n=='User')
                await conn.execute(add_hash_user_id(user['hashUserId'],uid))
            else:
                await create_default_user_data(conn,uid,a.name)
                from starter_music import grant_starter_music
                await grant_starter_music(conn, uid)
                if starter_tickets:
                    from helpers.things import grant_things_consolidated
                    await grant_things_consolidated(conn,uid,[(1,130001,starter_tickets)])
                await conn.execute(add_hash_user_id(hash_id(uid),uid))
        restored=await user_data(app,uid)
        state,credentials=transfer_config(uid,'import' if raw else 'fresh',bridge)
        if raw is None: state['accept_registration_name'] = True
        if raw:
            p=PRIVATE/'account-snapshot/user-data.response.bin';p.parent.mkdir(exist_ok=True);p.write_bytes(raw);p.chmod(0o600)
            write(PRIVATE/'imported-user-roundtrip.json',json.dumps(to_json(restored)))
        write(PRIVATE/'linking-credentials.txt',credentials)
        write(PRIVATE/'account.json',json.dumps(state,indent=2))
        print('Account ready. Linking credentials: private/linking-credentials.txt')
        print('Same-installation login bridge: '+('available' if bridge else 'absent; use Data Link on a compatible client'))
        if raw is None: print(f'Fresh account receives {starter_tickets:,} song tickets (歌劇目録) plus upstream starter inventory. It is NOT an unlock-all account; device onboarding remains experimental.')
    finally:await app.close()

def doctor(a):
    bootstrap()
    required=[VENDOR/'config.yml',PRIVATE/'upstream/master-original.db',PRIVATE/'upstream/master-manifest.json',PRIVATE/'account.json']
    failed=False
    for p in required:
        ok=p.is_file();print(('OK      ' if ok else 'MISSING ')+str(p.relative_to(ROOT)));failed|=not ok
    for kind in ['2d-assets','3d-assets','cri-assets']:
        p=VENDOR/'_data/assets'/kind/'ios/catalog.json'
        print(('OK      ' if p.exists() else 'WARNING ')+f'{kind} iOS catalog')
    for label,p,glob in [('charts',VENDOR/'_data/assets/Notations','*.enc'),('scenes',PRIVATE/'upstream/scenes','*'),('static media',PRIVATE/'static-assets','*')]:
        print(f'{label}: {sum(x.is_file() for x in p.rglob(glob)) if p.exists() else 0} local files (count does not prove completeness)')
    if not failed:
        import yaml,asyncpg
        c=yaml.safe_load((VENDOR/'config.yml').read_text())['database']
        async def check():
            conn=await asyncpg.connect(host=c['host'],port=c['port'],database=c['database'],user=c['username'],password=c['password'])
            try:
                uid=json.loads((PRIVATE/'account.json').read_text())['user_id']
                if not await conn.fetchval('SELECT count(*) FROM accounts WHERE "userId"=$1',uid):raise RuntimeError('Configured account missing')
            finally:await conn.close()
        asyncio.run(check());print('OK      database account')
    if failed:raise RuntimeError('Setup incomplete; see README')

def ensure_start_account():
    if not (PRIVATE/'account.json').exists():
        print('No account configured; creating a local Player starter save.')
        asyncio.run(account(argparse.Namespace(command='fresh-account', name='Player')))

def start(a):
    ensure_start_account()
    doctor(a)
    env=dict(os.environ,YUMESUTE_PORT=str(a.port))
    logdir=ROOT/'logs';logdir.mkdir(exist_ok=True)
    with (logdir/'backend.log').open('a') as log:
        backend=subprocess.Popen([sys.executable,str(ROOT/'tools/serve.py')],cwd=ROOT,env=env,stdout=log,stderr=log)
        try:
            import httpx
            for _ in range(100):
                if backend.poll() is not None:raise RuntimeError('Backend exited; see logs/backend.log')
                try:
                    r=httpx.get(f'http://127.0.0.1:{a.port}/api/Environment/Ping',timeout=1)
                    if r.status_code==200 and r.headers.get('X-Yumesute-Backend')=='local-preservation':break
                except httpx.HTTPError:pass
                time.sleep(.1)
            else:raise RuntimeError('Backend startup timed out')
            from tunnel import run
            asyncio.run(run(a))
        finally:
            backend.terminate()
            try:backend.wait(timeout=10)
            except subprocess.TimeoutExpired:backend.kill();backend.wait()

def main():
    os.chdir(ROOT);os.umask(0o077)
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('prepare');p.add_argument('--data-dir',required=True)
    p=sub.add_parser('import-account');p.add_argument('archive',type=Path)
    p=sub.add_parser('fresh-account');p.add_argument('--name',default='Player')
    sub.add_parser('doctor')
    p=sub.add_parser('start');p.add_argument('--ca-dir',help='Reuse an existing local mitmproxy CA directory; saved for future starts');p.add_argument('--host');p.add_argument('--port',type=int,default=8125);p.add_argument('--wg-port',type=int,default=51822);p.add_argument('--cert-port',type=int,default=8766);p.add_argument('--no-browser',action='store_true')
    a=parser.parse_args();PRIVATE.mkdir(exist_ok=True,mode=0o700)
    if a.command=='prepare':prepare(a)
    elif a.command in ('import-account','fresh-account'):asyncio.run(account(a))
    elif a.command=='doctor':doctor(a)
    else:start(a)

if __name__=='__main__':
    try:main()
    except KeyboardInterrupt:print('Stopped. Turn off the device WireGuard tunnel.')
    except Exception as e:
        print(f'Stopped: {type(e).__name__}: {e}',file=sys.stderr);sys.exit(1)
