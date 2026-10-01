"""Integration check on a disposable clone. Never run against a player's DB."""
import sys,asyncio,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'vendor/server-of-dreams')]
from helpers.config import database
database.database='yumesute_reroll_checks'
from serve import app,ACCOUNT
from helpers.auth import make_session_jwt
from helpers.gacha import detail_of
from scripts._sirius import _unpack_all,_decompress
from db.user import increment_item_stock
import httpx

def decode(r):
 r.raise_for_status();return [_decompress(x) for x in _unpack_all(r.content)]
async def main():
 assert app.config.database=='yumesute_reroll_checks'
 async with app.router.lifespan_context(app):
  uid=ACCOUNT['user_id'];g,d=detail_of(193300)
  async with app.acquire_db() as c:
   await c.conn.execute('DELETE FROM preservation_reroll');await c.conn.execute('DELETE FROM gacha_re_roll')
   await c.execute(increment_item_stock(uid,d.required_ticket_m_item_id,2))
   async def snapshot():
    return {t:[dict(x) for x in await c.conn.fetch('SELECT * FROM "'+t+'" ORDER BY "rowId"')] for t in ['character','item','gacha_history','gacha']}
   before=await snapshot()
  async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test',headers={'Authorization':'Bearer '+make_session_jwt(uid,'AppStore')}) as client:
   listing=decode(await client.get('/api/Gachas'));assert 1933 in [r[0] for r in listing[1]];assert any(x[0]==183 for x in listing[2])
   async def post(action):return decode(await client.post('/api/Gachas/'+action+'?gachaDetailMasterId=193300'))
   missing=await post('DecideReRollGacha');assert missing[0]
   # An unauthenticated request cannot create a session.
   anonymous=decode(await client.post('/api/Gachas/ReRoll?gachaDetailMasterId=193300',headers={'Authorization':''}));assert anonymous[0]
   first=await post('ReRoll');assert not first[0],first[0];assert len(first[1][1])==10
   same=decode(await client.post('/api/Gachas/Roll/193300'));assert same[1]==first[1]
   again=await post('GetReRollGachaResults');assert again[1]==first[1]
   async with app.acquire_db() as c:
    pending=await snapshot();assert pending['character']==before['character'];assert pending['gacha_history']==before['gacha_history'];assert pending['gacha']==before['gacha']
    row=await c.conn.fetchrow('SELECT * FROM preservation_reroll');ids=json.loads(row['prizes']);pool={x.id_:x for x in g.things}
    from helpers.cache import cache
    rarities={x.id_:int(x.rarity) for x in cache.character_master}
    assert any(rarities[pool[i].thing_id]==4 for i in ids)
   # Simulate backend restart by closing/reopening its database pool.
   await app.close();await app.yume_setup()
   assert (await post('GetReRollGachaResults'))[1]==first[1]
   # Finite limits and null/unlimited limits use the master's configured value.
   original_limit=g.re_roll_limit;g.re_roll_limit=0
   assert (await post('ReRoll'))[0]
   g.re_roll_limit=original_limit
   second=await post('ReRoll');assert not second[0]
   async with app.acquire_db() as c:
    rerolled=await snapshot();assert pending==rerolled
   # Concurrent confirmations must not grant twice.
   confirms=await asyncio.gather(post('DecideReRollGacha'),post('DecideReRollGacha'));assert all(x[1][0] for x in confirms)
   async with app.acquire_db() as c:
    final=await snapshot();assert len(final['gacha_history'])-len(before['gacha_history'])==10
    assert await c.conn.fetchval('SELECT decided FROM preservation_reroll')
   assert (await post('DecideReRollGacha'))[1][0]
   assert (await post('ReRoll'))[0]
   async with app.acquire_db() as c:assert final==await snapshot()
   print('PASS: entry, persistent retrieval, no preview grants, guaranteed Rare4, no reroll charge, concurrent/idempotent confirmation, decided rejection')
asyncio.run(main())
