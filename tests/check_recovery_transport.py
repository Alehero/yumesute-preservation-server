"""Offline official-protocol checks using a real private snapshot and MockTransport."""
import asyncio,sys,argparse
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'vendor/server-of-dreams'),str(ROOT)]
import httpx,msgpack
from models import AuthenticatePayload,TakeOverAccountPayload
from official_recovery import OfficialClient,Unavailable,Rejected,RecoveryError
from protocol import envelope

def reply(result,faults=None):return b''.join(msgpack.packb(x,use_bin_type=True) for x in [faults or [],result,[],[],[]])

async def main(raw):
    user=next(x[1] for x in envelope(raw)[1] if x and x[0]==0)
    calls=[]
    def happy(r):
        calls.append(r.url.path)
        assert r.headers['X-Platform']=='app-store'
        assert r.headers['X-FM']=='0'
        assert r.url.host=='lb-api.wds-stellarium.com'
        if r.url.path.endswith('GetTakeOverAccount'):return httpx.Response(200,content=reply([True,user[13],'Player',1,'login-secret']))
        if r.url.path.endswith('Authenticate'):
            assert msgpack.unpackb(r.content)[0]=='login-secret'
            return httpx.Response(200,content=reply(['session-secret',0,None]))
        assert r.headers['authorization']=='Bearer session-secret'
        return httpx.Response(200,content=raw)
    transfer=TakeOverAccountPayload(linkage_code='code',password='password')
    body,token=await OfficialClient(httpx.MockTransport(happy)).recover(transfer=transfer)
    assert body==raw and token=='login-secret' and len(calls)==3
    cases=[
        (httpx.Response(503),Unavailable),
        (httpx.Response(403),RecoveryError),
        (httpx.Response(302,headers={'Location':'https://elsewhere.invalid'}),RecoveryError),
        (httpx.Response(200,content=b'not msgpack'),RecoveryError),
        (httpx.Response(200,content=reply([False,None,None,0,None])),Rejected),
        (httpx.Response(200,content=reply(None,[['AccountNotFound','invalid','']])),Rejected),
        (httpx.Response(200,content=reply(None,[['EndOfService','closed','']])),Unavailable),
        (httpx.Response(200,content=reply(None,[['UnknownFault','unknown','']])),Rejected),
    ]
    for response,error in cases:
        try:await OfficialClient(httpx.MockTransport(lambda r:response)).recover(transfer=transfer)
        except error:pass
        else:raise AssertionError('Misclassified response')
    def timeout(r):raise httpx.ReadTimeout('timeout')
    try:await OfficialClient(httpx.MockTransport(timeout)).recover(transfer=transfer)
    except Unavailable:pass
    else:raise AssertionError('Timeout not classified')
    print('PASS: transfer/auth/data protocol, rejection vs outage, EOS, redirects, malformed replies, timeout')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--snapshot',required=True);a=p.parse_args()
    asyncio.run(main(Path(a.snapshot).read_bytes()))
