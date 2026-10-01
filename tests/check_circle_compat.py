"""Read-only Circle response checks against the pinned models and MessagePack schema.
Run from a prepared checkout: uv run --locked python tests/check_circle_compat.py
No official network or real account/database writes are used.
"""
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'vendor/server-of-dreams'),str(ROOT)]
import httpx
import msgpack
from fastapi import FastAPI
from helpers.auth import make_jwt
from helpers.msgpack import pack
from models import CirclePayload
from protocol import envelope
from routes.circles import router as upstream_router
import circle_compat

async def main():
    rows=[]
    async def fetch(query,uid):
        assert uid==123
        assert 'WHERE "userId"=$1' in query
        return rows
    @asynccontextmanager
    async def acquire():yield SimpleNamespace(conn=SimpleNamespace(fetch=fetch))
    app=FastAPI();app.acquire_db=acquire
    app.include_router(upstream_router)
    circle_compat.install(app)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test',headers={'Authorization':'Bearer '+make_jwt(123)}) as client:
        async def result(method,path,body=None):
            response=await client.request(method,path,content=body)
            assert response.status_code==200,(path,response.status_code)
            return envelope(response.content)[1]
        for path in ['/api/Circles','/api/Circles/Invited','/api/Circles/Search?circleName=test']:
            assert await result('GET',path)==[],path
        assert await result('POST','/api/Circles/Condition',pack(CirclePayload()))==[]
        assert (await result('POST','/api/Circles?circleId=missing'))[9]==19
        member=await result('GET','/api/Circles/MemberInfo?circleId=missing')
        assert member[0]==[] and member[1]==19
        mine=await result('POST','/api/Circles/MyCircleInfo')
        assert mine[8]==19 and mine[0] is None
        support=await result('GET','/api/Circles/GetSupportAndTheaterLevelInformation')
        assert len(support)==4
        for company in support:
            assert company[0]==0 and company[1]==0 and company[3]==0
            assert company[4]==[0,[]]
            assert isinstance(company[2],msgpack.Timestamp)
        for period in ['Daily','Weekly','Monthly']:
            rank=await result('GET','/api/Circles/Ranking/'+period)
            assert rank[0]==[] and rank[1]==[]
        rows.append({'company':2,'level':7,'currentSupportPoint':80,'lastLevelUppedAt':1700000000123,'levelLimit':10})
        support=await result('GET','/api/Circles/GetSupportAndTheaterLevelInformation')
        assert support[1][:2]==[7,80] and support[1][3]==10
        assert support[1][2]==msgpack.Timestamp(1700000000,123000000)
        assert support[0][0]==0 and support[2][0]==0 and support[3][0]==0
        assert (await result('POST','/api/Circles/MyCircleInfo'))[12]==support
    print('PASS: compatibility route precedence, empty lists/rankings, missing-circle status, four non-null company results, account-scoped progress and millisecond timestamp serialization')

if __name__=='__main__':asyncio.run(main())
