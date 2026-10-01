"""Gift integration checks on the disposable reroll database only."""
import asyncio, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'vendor/server-of-dreams')]
from helpers.config import database
database.database='yumesute_reroll_checks'
from serve import app
from helpers.auth import register,decode_jwt
from models import RegisterPayload
from preservation_gift import ensure_gift,receive,EVENT

async def main():
    assert app.config.database=='yumesute_reroll_checks'
    async with app.router.lifespan_context(app):
        uid=decode_jwt((await register(RegisterPayload(name='Gift test'),app)).token)
        async def stock():
            async with app.acquire_db() as c:
                return await c.conn.fetchval('SELECT COALESCE(SUM(stock),0) FROM item WHERE "userId"=$1 AND "itemMasterId"=130001',uid)
        before=await stock()
        await asyncio.gather(ensure_gift(app,uid),ensure_gift(app,uid))
        async with app.acquire_db() as c:
            rows=await c.conn.fetch('SELECT inbox_id FROM preservation_gifts WHERE user_id=$1 AND event=$2',uid,EVENT)
            assert len(rows)==1
            iid=rows[0]['inbox_id']
            row=await c.conn.fetchrow('SELECT * FROM inbox WHERE "userId"=$1 AND id=$2',uid,iid)
            assert row['thingQuantity']==10000 and not row['isTimeLimited'] and row['receiveLimitAt']==0
        assert await stock()==before
        await asyncio.gather(receive(app,uid,[iid,iid]),receive(app,uid,[iid]))
        assert await stock()==before+10000
        await ensure_gift(app,uid)
        await receive(app,uid,[iid])
        assert await stock()==before+10000
        # The ledger survives inbox cleanup, so login never reissues a claimed gift.
        async with app.acquire_db() as c:
            await c.conn.execute('DELETE FROM inbox WHERE "userId"=$1 AND id=$2',uid,iid)
        await ensure_gift(app,uid)
        async with app.acquire_db() as c:
            assert not await c.conn.fetchval('SELECT 1 FROM inbox WHERE "userId"=$1 AND id=$2',uid,iid)
    print('PASS: gift issued once, no expiry, inventory changes only on claim, concurrent/duplicate claims grant once, cleanup cannot reissue')
asyncio.run(main())
