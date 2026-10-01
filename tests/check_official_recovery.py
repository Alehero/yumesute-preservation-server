"""Disposable PostgreSQL checks. Run with --snapshot PRIVATE_EXPORTED_RESPONSE.
Requires an empty schema in yumesute_recovery_checks; never uses official network.
"""
import asyncio,sys,argparse
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'vendor/server-of-dreams'),str(ROOT)]
from helpers.config import database
from helpers.cache import load_master_data
from helpers.auth import register,make_jwt,decode_jwt
from models import RegisterPayload,AuthenticatePayload,TakeOverAccountPayload
from core import YumeApp
from official_recovery import Recovery,Unavailable,Rejected,RecoveryError,credential_key
from protocol import inspect_snapshot

class Stub:
    def __init__(self,raw):self.raw=raw;self.calls=0;self.error=None
    async def recover(self,**kwargs):
        self.calls+=1
        if self.error:raise self.error
        return self.raw,'official-login-token'

async def main(raw):
    database.database='yumesute_recovery_checks'
    app=YumeApp(config=database);await app.yume_setup();load_master_data()
    async with app.acquire_db() as c:
        assert await c.conn.fetchval('SELECT count(*) FROM accounts')==0,'Use an empty disposable database'
    reg=await register(RegisterPayload(name='Starter'),app);starter=decode_jwt(reg.token)
    state={'mode':'fresh','user_id':starter};stub=Stub(raw);svc=Recovery(app,state,stub)
    # Unavailable officials select existing starter without changing its data.
    stub.error=Unavailable();fallback=AuthenticatePayload(login_token='outage-token')
    assert await svc.resolve(auth=fallback)==starter
    calls=stub.calls;assert await svc.resolve(auth=fallback)==starter and stub.calls==calls
    # Wrong credentials and unknown failures cannot fall back or create identities.
    for error in [Rejected(),RecoveryError()]:
        stub.error=error
        try:await svc.resolve(auth=AuthenticatePayload(login_token='bad-token'))
        except type(error):pass
        else:raise AssertionError('Failure was swallowed')
        assert await svc.lookup(credential_key('token','bad-token')) is None
    stub.error=None
    # Simulate a database failure after account creation: every write must roll back.
    from unittest.mock import patch
    from helpers import user_data as data_helpers
    async def broken_baseline(*args):raise RuntimeError('simulated import failure')
    with patch.object(data_helpers,'build_present',broken_baseline):
        try:await svc.resolve(auth=AuthenticatePayload(login_token='rollback-token'))
        except RuntimeError:pass
        else:raise AssertionError('Injected failure was swallowed')
    async with app.acquire_db() as c:
        assert await c.conn.fetchval('SELECT count(*) FROM accounts')==1
        assert await c.conn.fetchval('SELECT count(*) FROM preservation_recovery')==0
    assert await svc.lookup(credential_key('token','rollback-token')) is None
    transfer=TakeOverAccountPayload(linkage_code='test-official-id',password='test-password')
    uids=await asyncio.gather(*(svc.resolve(transfer=transfer) for _ in range(3)))
    uid=uids[0];assert all(x==uid for x in uids)
    assert uid==inspect_snapshot(raw)['user_id']
    assert uid!=starter
    async with app.acquire_db() as c:
        await c.conn.execute('UPDATE "user" SET "playerRank"=123 WHERE "userId"=$1',uid)
        before=await c.conn.fetchval('SELECT count(*) FROM character WHERE "userId"=$1',uid)
    # True EOS: any network call is a test failure, including after service restart.
    stub.error=AssertionError('Official contacted for a local account');calls=stub.calls
    svc=Recovery(app,state,stub)
    assert await svc.resolve(transfer=transfer)==uid
    assert await svc.resolve(auth=AuthenticatePayload(login_token='official-login-token'))==uid
    assert await svc.resolve(auth=AuthenticatePayload(login_token=make_jwt(uid)))==uid
    assert stub.calls==calls
    # Recovering same identity via another valid credential cannot overwrite local progress.
    stub.error=None
    assert await svc.resolve(auth=AuthenticatePayload(login_token='second-official-token'))==uid
    async with app.acquire_db() as c:
        assert await c.conn.fetchval('SELECT "playerRank" FROM "user" WHERE "userId"=$1',uid)==123
        assert await c.conn.fetchval('SELECT count(*) FROM character WHERE "userId"=$1',uid)==before
    # Once recovered, an unknown credential plus outage must not pick a starter.
    stub.error=Unavailable()
    try:await svc.resolve(auth=AuthenticatePayload(login_token='new-unknown-token'))
    except Unavailable:pass
    else:raise AssertionError('Recovered installation fell back')
    assert await svc.lookup(credential_key('token','new-unknown-token')) is None
    # Invalid snapshot cannot link a credential or alter either account.
    stub.error=None;stub.raw=b'bad'
    try:await svc.resolve(auth=AuthenticatePayload(login_token='malformed-snapshot'))
    except (ValueError,RecoveryError):pass
    else:raise AssertionError('Malformed snapshot accepted')
    assert await svc.lookup(credential_key('token','malformed-snapshot')) is None
    async with app.acquire_db() as c:assert await c.conn.fetchval('SELECT count(*) FROM accounts')==2
    await app.close()
    # Exercise the real HTTP routes against the persisted save with official calls forbidden.
    import httpx
    import serve
    from helpers.msgpack import pack
    from protocol import envelope
    stub.error=AssertionError('Official contacted during local HTTP login')
    serve.RECOVERY=Recovery(serve.app,state,stub)
    async with serve.app.router.lifespan_context(serve.app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=serve.app),base_url='http://test') as client:
            response=await client.post('/api/Account/GetTakeOverAccount',content=pack(transfer))
            result=envelope(response.content)[1];assert result[0] is True
            response=await client.post('/api/Account/Authenticate',content=pack(AuthenticatePayload(login_token=result[4])))
            session=envelope(response.content)[1][0]
            response=await client.get('/api/data/user',headers={'Authorization':'Bearer '+session})
            users=[x[1] for x in envelope(response.content)[1] if x and x[0]==0]
            assert len(users)==1 and users[0][0]==uid
            from import_account import row_dict
            assert row_dict('User',users[0])['playerRank']==123
    print('PASS: recovery, persisted local-only EOS login, no overwrite, bad credentials, outage fallback, malformed response, and save preservation')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--snapshot',required=True);args=p.parse_args()
    asyncio.run(main(Path(args.snapshot).read_bytes()))
