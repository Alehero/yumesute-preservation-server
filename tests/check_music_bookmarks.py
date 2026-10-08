"""Offline integration checks. Requires a disposable clone with two accounts."""
import argparse,asyncio,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'vendor/server-of-dreams'),str(ROOT)]
import httpx
from helpers.config import database
from helpers.cache import load_master_data,cache
from helpers.auth import make_jwt
from helpers.msgpack import pack
from helpers.user_data import build_present
from protocol import envelope
from core import YumeApp
from official_recovery import Recovery
from routes.lives import router as lives
from routes.multi_room import router as rooms
from music_bookmark_compat import install as bookmarks
from room_compat import install as room_list

async def main(name):
    assert name.startswith('yumesute_pr5_checks_'),'Use a disposable database clone'
    database.database=name
    app=YumeApp(config=database);await app.yume_setup();load_master_data()
    app.include_router(lives);app.include_router(rooms);bookmarks(app);room_list(app)
    async with app.acquire_db() as c:
        ids=await c.conn.fetch('SELECT "userId" FROM accounts ORDER BY "userId" LIMIT 2')
        assert len(ids)==2
        one,two=[r['userId'] for r in ids]
        songs=[m.id_ for m in cache.music_master if not m.invisible][:2];song,other=songs
        await c.conn.execute('DELETE FROM music_bookmark WHERE "userId"=ANY($1::bigint[]) AND "musicMasterId"=ANY($2::int[])',[one,two],songs)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
        async def edit(uid,song,flag):
            r=await client.post('/api/Lives/Music/EditBookmark',content=pack([song,flag]),headers={'Authorization':'Bearer '+make_jwt(uid)} if uid else {})
            assert r.status_code==200
            return envelope(r.content)
        r=await client.get('/api/MultiRooms');assert r.status_code==200 and envelope(r.content)==[[],[],[],[],[]]
        assert (await edit(None,song,1))[1]==[False]
        for music,flag in [(song,-1),(song,8),(song,2**40),(0,1),(2147483647,1)]:
            assert (await edit(one,music,flag))[1]==[False]
        assert (await edit(one,song,0))[2]==[]
        for flag in [1,2,4,7]:
            r=await edit(one,song,flag);assert r[1]==[True] and r[2]==[[146,[song,flag]]]
        await edit(two,song,2);await edit(one,other,4)
        await asyncio.gather(*(edit(one,song,3) for _ in range(12)))
        async with app.acquire_db() as c:
            assert await c.conn.fetchval('SELECT count(*) FROM music_bookmark WHERE "userId"=$1 AND "musicMasterId"=$2',one,song)==1
            await c.conn.execute('INSERT INTO music_bookmark ("userId","musicMasterId","musicBookmarkFlag") VALUES($1,$2,7)',one,song)
        assert (await edit(one,song,0))[2]==[[146,[song,0]]]
        async with app.acquire_db() as c:
            rows=await c.conn.fetch('SELECT "musicBookmarkFlag" FROM music_bookmark WHERE "userId"=$1 AND "musicMasterId"=$2',one,song)
            assert len(rows)==1 and rows[0][0]==0
            assert await c.conn.fetchval('SELECT "musicBookmarkFlag" FROM music_bookmark WHERE "userId"=$1 AND "musicMasterId"=$2',two,song)==2
    # New DB pool simulates reload; compatibility overlays must retain bookmark edits.
    await app.close();app=YumeApp(config=database);await app.yume_setup()
    recovery=Recovery(app,{'mode':'fresh','user_id':one})
    for uid in [one,two]:
        current=await build_present(app,uid,'MusicBookmark')
        # Full original snapshot may include other types; only check the bookmark under test.
        merged=await recovery.merge(uid,current)
        found=[r for r in merged if r and r[0]==146 and r[1][0]==song]
        assert found==[[146,[song,0 if uid==one else 2]]],found
    await app.close()
    print('PASS: room route precedence/envelope; bookmark flags, invalid input, add/update/remove, concurrent edits, duplicate cleanup, account/song isolation and reload/overlay persistence')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--database',required=True);args=p.parse_args();asyncio.run(main(args.database))
