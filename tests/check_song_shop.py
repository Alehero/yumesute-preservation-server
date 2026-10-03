"""Regression checks on a disposable clone named yumesute_shop_regression_20261003."""
import asyncio,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'vendor/server-of-dreams'),str(ROOT)]
from helpers.config import database
from helpers.cache import load_master_data
from helpers.auth import make_jwt
from helpers.music_unlock import load_progress
from core import YumeApp
from starlette.requests import Request
from gameplay import buy_chart
from protocol import envelope
from starter_music import ensure_starter_music
from live_drop_windows import install

async def main():
    database.database='yumesute_shop_regression_20261003'
    app=YumeApp(config=database);await app.yume_setup();load_master_data()
    async with app.acquire_db() as c:
        identities=await c.conn.fetch("SELECT user_id FROM preservation_recovery")
        assert len(identities)==1,"Use a disposable clone with one recovered account"
        UID=identities[0]["user_id"]
    async with app.acquire_db() as c:
        assert await c.conn.fetchval('SELECT count(*) FROM music WHERE "userId"=$1 AND "musicMasterId" IN (224,237,260)',UID)==0
        progress=await load_progress(c,UID);assert progress.max_cleared_olivier_level>=104
        old=[dict(x) for x in await c.conn.fetch('SELECT * FROM music WHERE "userId"=$1 ORDER BY id',UID)]
    await ensure_starter_music(app,UID,{'mode':'fresh','user_id':1})
    async with app.acquire_db() as c:
        for row in old:
            current=await c.conn.fetchrow('SELECT * FROM music WHERE "userId"=$1 AND id=$2',UID,row['id'])
            assert dict(current)==row,'Existing progression overwritten'
        count=await c.conn.fetchval('SELECT count(*) FROM music WHERE "userId"=$1',UID)
    await ensure_starter_music(app,UID,{'mode':'fresh','user_id':1})
    async with app.acquire_db() as c:assert await c.conn.fetchval('SELECT count(*) FROM music WHERE "userId"=$1',UID)==count
    def request():return Request({'type':'http','method':'POST','path':'/api/Shops/ExchangeMusicScore/22405','headers':[(b'authorization',('Bearer '+make_jwt(UID)).encode())],'app':app})
    async def balance():
        async with app.acquire_db() as c:return await c.conn.fetchval('SELECT stock FROM item WHERE "userId"=$1 AND "itemMasterId"=130001',UID)
    for chart in [22405,23705,26005]:
        before=await balance();response=envelope((await buy_chart(request(),chart)).body)
        assert response[1]==[True],(chart,response[1]);assert await balance()==before-1
        assert envelope((await buy_chart(request(),chart)).body)[1]==[False]
        assert await balance()==before-1,'Repeated purchase charged twice'
    async with app.acquire_db() as c:
        await c.conn.execute('UPDATE music SET "olivierReleaseStatus"=2 WHERE "userId"=$1 AND "musicMasterId"=260',UID)
        await c.conn.execute('UPDATE item SET stock=0 WHERE "userId"=$1 AND "itemMasterId"=130001',UID)
    assert envelope((await buy_chart(request(),26005)).body)[1]==[False]
    async with app.acquire_db() as c:assert await c.conn.fetchval('SELECT "olivierReleaseStatus" FROM music WHERE "userId"=$1 AND "musicMasterId"=260',UID)==2
    from routes import lives
    kwargs=dict(stamina_consumed=True,score=10000000,star_act_count=10,achievement_rate=100)
    before=lives.resolve_frames(1,**kwargs);install();after=lives.resolve_frames(1,**kwargs)
    assert len(after)<len(before) and after
    assert not any(r.thing_id in (212001,137001,137007,137051,132052,132053) for f in after for r in f.rewards or [])
    await app.close()
    print('PASS: imported default ownership, unchanged existing progression, idempotence, three OLIVIER purchases, duplicate/insufficient-ticket protection, expired live-drop exclusion with permanent rewards retained')
if __name__=='__main__':asyncio.run(main())
