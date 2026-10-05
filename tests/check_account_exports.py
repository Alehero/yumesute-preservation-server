"""Offline integration checks against an explicitly named disposable save clone."""
import argparse,asyncio,json,re,sys,tempfile,zipfile,io
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'vendor/server-of-dreams'),str(ROOT)]
import httpx
from fastapi import FastAPI
from helpers.config import database
from helpers.user_data import user_data
from helpers.auth import make_jwt
from helpers.msgpack import respond
from core import YumeApp
from official_recovery import Recovery,Unavailable,credential_key
from recovery_page import install
from token_vault import TokenVault,open_portable
from protocol import envelope

class Official:
    calls=0
    async def recover(self,**kwargs):
        self.calls+=1
        raise Unavailable()

async def main(name):
    assert name.startswith('yumesute_export_checks_'),'Use a disposable clone'
    database.database=name
    db=YumeApp(config=database);await db.yume_setup()
    async with db.acquire_db() as c:
        uid=await c.conn.fetchval('SELECT user_id FROM preservation_recovery LIMIT 1')
        assert uid
        before=await c.conn.fetchval('SELECT "playerRank" FROM "user" WHERE "userId"=$1',uid)
        await c.conn.execute("INSERT INTO preservation_credentials VALUES($1,$2,'official') ON CONFLICT DO NOTHING",credential_key('token','fake-previously-official'),uid)
        await c.conn.execute("INSERT INTO preservation_credentials VALUES($1,$2,'starter-fallback') ON CONFLICT DO NOTHING",credential_key('token','fake-fallback'),uid)
    with tempfile.TemporaryDirectory() as folder:
        vault=TokenVault(folder);official=Official();recovery=Recovery(db,{'mode':'fresh','user_id':1,'transfer':{'code':'local'}},official,vault)
        await recovery.setup();vault.enable(True)
        assert await recovery.local_token_uid(make_jwt(uid))==uid and not vault.has(uid)
        assert await recovery.local_token_uid('fake-fallback')==uid and not vault.has(uid)
        assert await recovery.local_token_uid('fake-previously-official')==uid and vault.has(uid)
        assert official.calls==0
        async def snapshot(bound,uid):return await recovery.merge(uid,await user_data(bound,uid))
        expected=respond(await snapshot(db,uid)).body
        app=FastAPI();install(app,recovery,Path(folder),8125,snapshot)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://127.0.0.1:8125') as client:
            page=await client.get('/recovery');csrf=re.search("const csrf='([^']+)'",page.text)[1]
            h={'Origin':'http://127.0.0.1:8125','X-Recovery-Token':csrf}
            assert (await client.post('/recovery/local',json={'action':'save','user_id':str(uid)})).status_code==403
            assert (await client.get('/recovery/accounts',headers={'host':'evil.test'})).status_code==403
            listing=(await client.get('/recovery/accounts')).json()
            assert any(a['id']==str(uid) and a['credential_saved'] for a in listing['accounts'])
            r=await client.post('/recovery/local',json={'action':'save','user_id':str(uid)},headers=h)
            assert r.status_code==200,r.text
            with zipfile.ZipFile(io.BytesIO(r.content)) as z:
                assert envelope(z.read('user-data.response.bin'))==envelope(expected)
                assert 'unverified-progress' in json.loads(z.read('manifest.json'))['source']
                assert b'fake-previously-official' not in b''.join(z.read(n) for n in z.namelist())
            r=await client.post('/recovery/local',json={'action':'credential','user_id':str(uid),'passphrase':'test backup passphrase'},headers=h)
            assert r.status_code==200
            assert open_portable(r.content,'test backup passphrase')['official_login_token']=='fake-previously-official'
            assert (await client.post('/recovery/local',json={'action':'credential','user_id':str(uid),'passphrase':'short'},headers=h)).status_code==400
            r=await client.post('/recovery/export',json={'code':'official','password':'test-password'},headers=h)
            assert r.status_code==400
            # Re-retrieve an official credential without importing or overwriting progress.
            class Online:
                async def recover(self,**kwargs):return expected,'fresh-official-token'
            recovery.official=Online()
            r=await client.post('/recovery/export',json={'code':'official','password':'test-password'},headers=h)
            assert r.status_code==200 and vault.read(uid)['official_login_token']=='fresh-official-token'
            assert await recovery.local_token_uid('fake-previously-official')==uid
            async with db.acquire_db() as c:
                assert await c.conn.fetchval('SELECT "playerRank" FROM "user" WHERE "userId"=$1',uid)==before
        # Unknown credential recovery preserves its token after an insert-only import.
        from models import AuthenticatePayload
        assert await recovery.resolve(auth=AuthenticatePayload(login_token='new-test-token'))==uid
        assert vault.read(uid)['official_login_token']=='fresh-official-token'
    await db.close()
    print('PASS: current merged save ZIP, credential encryption, CSRF/host checks, no local-token/fallback capture, local-first EOS, progress unchanged')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--database',required=True);args=p.parse_args();asyncio.run(main(args.database))
