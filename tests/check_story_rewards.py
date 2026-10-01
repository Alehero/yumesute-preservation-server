"""Destructive integration checks ONLY in a disposable yumesute_release_rewards DB.
Pass the path of an isolated, prepared fresh-account test installation. Never use a save.
"""
import asyncio
from collections import Counter
import json
from pathlib import Path
import sys
import yaml

async def main(root):
    config=yaml.safe_load((root/'vendor/server-of-dreams/config.yml').read_text())
    if config['database']['database'] != 'yumesute_release_rewards':
        raise RuntimeError('Refusing anything except the dedicated yumesute_release_rewards test database')
    sys.path.insert(0,str(root));sys.path.insert(0,str(root/'tools'));sys.path.insert(0,str(root/'vendor/server-of-dreams'))
    from core import YumeApp
    from helpers.config import database
    from helpers.cache import load_master_data, cache
    from helpers.auth import make_jwt
    from helpers.episodes import episode_read_reward_things, episode_readall_reward_things
    from helpers.things import grant_things_consolidated
    from gameplay import read_story, buy_music
    from protocol import envelope
    from starlette.requests import Request
    load_master_data();app=YumeApp(config=database);await app.yume_setup()
    uid=json.loads((root/'private/account.json').read_text())['user_id']
    req=Request({'type':'http','app':app,'headers':[(b'authorization',('Bearer '+make_jwt(uid)).encode())]})
    async def balance():
        async with app.acquire_db() as conn:
            rows=await conn.conn.fetch('SELECT "itemMasterId",stock FROM item WHERE "userId"=$1',uid)
            c=await conn.conn.fetchrow('SELECT coin,"freeJewel" FROM currency WHERE "userId"=$1',uid)
        return Counter({**{(1,r['itemMasterId']):r['stock'] for r in rows},(12,0):c['coin'],(13,0):c['freeJewel']})
    def expect_delta(before,after,things):
        expected=Counter()
        for kind,ident,amount in things:
            assert kind in (1,12,13), 'Select an item/currency-only episode for this test'
            expected[(kind,ident if kind==1 else 0)]+=amount
        actual=Counter({k:after[k]-before[k] for k in set(before)|set(after) if after[k]!=before[k]})
        assert actual==expected,(actual,expected)
    async def call(eid,full):
        response=await read_story(req,eid,full)
        parsed=envelope(response.body)
        assert not parsed[0], 'Response fault'
        return parsed[1]
    try:
        from preservation_gift import ensure_gift, receive, EVENT
        await ensure_gift(app,uid)
        async with app.acquire_db() as c:
            gift=await c.conn.fetchval('SELECT inbox_id FROM preservation_gifts WHERE user_id=$1 AND event=$2',uid,EVENT)
        await receive(app,uid,[gift])
        initial=await balance();assert initial[(1,130001)]>=10000
        print('PASS: account can claim 10,000 song tickets')
        song=next(m for m in cache.music_master if not m.invisible and int(m.unlock_condition_type)==10)
        response=await buy_music(req,song.id_);assert not envelope(response.body)[0]
        after_buy=await balance();assert after_buy[(1,130001)]==initial[(1,130001)]-10
        async with app.acquire_db() as conn:
            assert await conn.conn.fetchval('SELECT "isPossession" FROM music WHERE "userId"=$1 AND "musicMasterId"=$2',uid,song.id_)
        print('PASS: song purchase grants ownership and consumes 10 tickets')
        async with app.acquire_db() as conn:
            read_ids={r[0] for r in await conn.conn.fetch('SELECT "episodeMasterId" FROM episode WHERE "userId"=$1',uid)}
        candidates=[e.id_ for e in cache.episode_master if e.id_ not in read_ids and episode_read_reward_things(e.id_) and episode_readall_reward_things(e.id_) and all(t[0] in (1,12,13) for t in episode_read_reward_things(e.id_))]
        first,second=candidates[:2]
        before=await balance();result=await call(first,False);after=await balance()
        expect_delta(before,after,episode_read_reward_things(first));assert result
        before=after;assert await call(first,False)==[];assert await balance()==before
        result=await call(first,True);after=await balance();expect_delta(before,after,episode_readall_reward_things(first));assert result
        before=after;assert await call(first,True)==[];assert await balance()==before
        before=await balance();result=await call(second,True);after=await balance()
        expect_delta(before,after,episode_read_reward_things(second)+episode_readall_reward_things(second));assert result
        assert await call(second,False)==[];assert await balance()==after
        async with app.acquire_db() as conn:
            assert await conn.conn.fetchval('SELECT "hasReadAll" FROM episode WHERE "userId"=$1 AND "episodeMasterId"=$2',uid,first)
            assert await conn.conn.fetchval('SELECT "hasReadAll" FROM episode WHERE "userId"=$1 AND "episodeMasterId"=$2',uid,second)
        print('PASS: first skip/read reward, full-read follow-up, direct full read, repeat reward suppression, persisted flags')
        async with app.acquire_db() as conn:
            owned={r['characterMasterId'] for r in await conn.conn.fetch('SELECT "characterMasterId" FROM character WHERE "userId"=$1',uid)}
        side=next(e for e in cache.character_episode_master if e.character_master_id in owned and int(e.episode_order)==1 and episode_read_reward_things(e.episode_master_id))
        before=await balance();assert await call(side.episode_master_id,False)==[];assert await balance()==before
        # Unlock only in this disposable test DB to isolate the read/reward path.
        async with app.acquire_db() as conn:
            await conn.conn.execute('UPDATE character SET "releasedEpisodeOrder"=1 WHERE "userId"=$1 AND "characterMasterId"=$2',uid,side.character_master_id)
        result=await call(side.episode_master_id,False);after=await balance()
        expect_delta(before,after,episode_read_reward_things(side.episode_master_id));assert result
        assert await call(side.episode_master_id,False)==[];assert await balance()==after
        async with app.acquire_db() as conn:
            assert await conn.conn.fetchval('SELECT "readEpisodeOrder" FROM character WHERE "userId"=$1 AND "characterMasterId"=$2',uid,side.character_master_id)==1
        print('PASS: locked side story rejected; unlocked side grants reward once and persists character reading progress')
        print('Test episodes:',first,second,'read rewards:',episode_read_reward_things(first),'full-read bonus:',episode_readall_reward_things(first))
    finally:await app.close()

if __name__=='__main__':
    asyncio.run(main(Path(sys.argv[1]).expanduser().resolve()))
