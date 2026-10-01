"""Offline browser-recovery checks, after check_official_recovery.py in its disposable DB."""
import asyncio,sys,argparse,re,json,tempfile,zipfile,io
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'vendor/server-of-dreams'),str(ROOT)]
import httpx
from fastapi import FastAPI
from helpers.config import database
from helpers.cache import load_master_data
from core import YumeApp
from official_recovery import Recovery,Unavailable,credential_key
from recovery_page import install
from protocol import inspect_snapshot
from exporter import verify_export

class Official:
    def __init__(self,raw):self.raw=raw;self.calls=0;self.offline=False
    async def recover(self,**kwargs):
        self.calls+=1
        if self.offline:raise Unavailable()
        return self.raw,'page-login-token'

async def main(raw):
    database.database='yumesute_recovery_checks'
    db=YumeApp(config=database);await db.yume_setup();load_master_data()
    official=Official(raw);state={'mode':'fresh','user_id':1,'transfer':{'code':'local-only-code'}}
    recovery=Recovery(db,state,official);await recovery.setup();uid=inspect_snapshot(raw)['user_id']
    key=credential_key('transfer',['page-official-code','test-password'])
    async with db.acquire_db() as c:
        assert await c.conn.fetchval('SELECT count(*) FROM accounts')==2
        await c.conn.execute("INSERT INTO preservation_credentials VALUES($1,1,'starter-fallback')",key)
    with tempfile.TemporaryDirectory() as folder:
        app=FastAPI();install(app,recovery,Path(folder),8125)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://127.0.0.1:8125') as client:
            for h in [{'host':'evil.test:8125'},{'sec-fetch-site':'cross-site'},{'host':'lb-api.wds-stellarium.com'}]:
                assert (await client.get('/recovery',headers=h)).status_code==403
            page=await client.get('/recovery');assert page.status_code==200
            assert page.headers['cache-control']=='no-store' and 'frame-ancestors' in page.headers['content-security-policy']
            token=re.search("const csrf='([^']+)'",page.text)[1]
            credentials={'code':'page-official-code','password':'test-password'}
            assert (await client.post('/recovery/export',json=credentials)).status_code==403
            h={'Origin':'http://127.0.0.1:8125','X-Recovery-Token':token}
            bad={**h,'Origin':'https://evil.test'}
            assert (await client.post('/recovery/export',json=credentials,headers=bad)).status_code==403
            assert official.calls==0
            assert (await client.post('/recovery/export',json={'code':'local-only-code','password':'test-password'},headers=h)).status_code==400
            assert official.calls==0
            official.offline=True
            assert (await client.post('/recovery/export',json=credentials,headers=h)).status_code==400
            assert await recovery.lookup(key)==1
            official.offline=False
            response=await client.post('/recovery/export',json=credentials,headers=h)
            assert response.status_code==200
            stage=response.headers['X-Recovery-Stage']
            with zipfile.ZipFile(io.BytesIO(response.content)) as z:
                assert json.loads(z.read('manifest.json'))['source']=='official-api-authenticated-recovery'
                assert z.read('user-data.response.bin')==raw
            files=list(Path(folder).rglob('*.zip'));assert len(files)==1;verify_export(files[0])
            assert await recovery.lookup(key)==1,'Downloading changed local account'
            assert (await client.post('/recovery/import',json={'stage':stage},headers=h)).status_code==400
            calls=official.calls
            response=await client.post('/recovery/import',json={'stage':stage,'confirm':True},headers=h)
            assert response.status_code==200,response.text
            assert official.calls==calls and await recovery.lookup(key)==uid
            async with db.acquire_db() as c:
                assert await c.conn.fetchval('SELECT count(*) FROM accounts')==2
                assert await c.conn.fetchval('SELECT "playerRank" FROM "user" WHERE "userId"=$1',uid)==123
            assert (await client.post('/recovery/import',json={'stage':stage,'confirm':True},headers=h)).status_code==400
    await db.close()
    print('PASS: browser origin/host/CSRF protection, official-only export, no-mutation download, verified ZIP, explicit fallback reassignment, no progress overwrite, single-use import')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--snapshot',required=True);a=p.parse_args();asyncio.run(main(Path(a.snapshot).read_bytes()))
