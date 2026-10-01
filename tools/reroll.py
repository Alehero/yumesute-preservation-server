"""Persistent local reroll sessions. Odds are preservation approximations, not official."""
import json
import time
import msgpack
from fastapi import APIRouter, Request
from helpers.auth import decode_jwt
from helpers.cache import cache
from helpers.gacha import active_gacha_ids, detail_of, roll_prizes, piece_bonus, _RATES
from helpers.msgpack import respond, fault
from helpers.things import grant_things_consolidated
from helpers.user_data import current_user_id, build_present
from models import GachaRollResult, GachaThingResult, BooleanResult
from db.user import add_gacha_rolls, add_gacha_historys
from routes.gachas import _spend_cost, _award_prize, _random_gacha_id, gachas_roll_gacha, gachas_get_available_gachas

# Master names explicitly promise >=1 Rare4; fixed slots must not use Rare3 fallback.
# Normal 82/15/3 odds and equal-within-rarity weighting are approximate.
_RATES[(9, 1)] = {'normal': {2: .82, 3: .15, 4: .03}, 'fixed': {2: 0., 3: 0., 4: 1.}, 'pickup': 0.}

async def state(conn, uid, gid, count=0, decided=False):
    existing=await conn.conn.fetchval('SELECT 1 FROM gacha_re_roll WHERE "userId"=$1 AND "gachaMasterId"=$2',uid,gid)
    if existing:
        await conn.conn.execute('UPDATE gacha_re_roll SET "rollCount"=$3,"isDecided"=$4 WHERE "userId"=$1 AND "gachaMasterId"=$2',uid,gid,count,decided)
    else:
        await conn.conn.execute('INSERT INTO gacha_re_roll ("userId","gachaMasterId","rollCount","isDecided") VALUES ($1,$2,$3,$4)',uid,gid,count,decided)


async def award(conn, uid, gacha, detail, prizes):
    results=[]
    for thing in prizes:
        received=await _award_prize(conn,uid,gacha,thing)
        extra=await grant_things_consolidated(conn,uid,piece_bonus(gacha,thing))
        results.append(GachaThingResult(received_things=received,additional_received_things=extra))
    bonus=await grant_things_consolidated(conn,uid,[(int(b.thing_type),b.thing_id,(b.thing_quantity or 0)*len(prizes)) for b in gacha.bonus_things])
    detail_bonus=await grant_things_consolidated(conn,uid,[(int(b.thing_type),b.thing_id,b.thing_quantity or 0) for b in detail.detail_bonus_things])
    return GachaRollResult(m_gacha_master_id=detail.id_,received_things=results,received_bonus_things=bonus,received_detail_bonus_things=detail_bonus,received_roll_bonus_things=[])


def install(app):
    async def setup():
        async with app.acquire_db() as c:
            await c.conn.execute('''CREATE TABLE IF NOT EXISTS preservation_reroll (
            user_id bigint NOT NULL REFERENCES accounts("userId"), banner_id bigint NOT NULL,
            detail_id bigint NOT NULL, prizes jsonb NOT NULL, preview bytea NOT NULL,
            roll_count int NOT NULL, decided boolean NOT NULL DEFAULT false,
            PRIMARY KEY(user_id,banner_id))''')

    from contextlib import asynccontextmanager
    previous = app.router.lifespan_context
    @asynccontextmanager
    async def lifespan(app):
        async with previous(app):
            await setup()
            yield
    app.router.lifespan_context = lifespan

    router=APIRouter()
    @router.get('/api/Gachas')
    async def listing(request: Request):
        uid=current_user_id(request)
        if uid is None: return respond([],faults=[fault('InvalidRequest')])
        active=set(active_gacha_ids())
        async with app.acquire_db() as c,c.transaction():
            await c.conn.execute('SELECT pg_advisory_xact_lock($1)',uid)
            for g in cache.gacha_master:
                if g.id_ in active and int(g.gacha_type)==9:
                    if not await c.conn.fetchval('SELECT 1 FROM gacha_re_roll WHERE "userId"=$1 AND "gachaMasterId"=$2',uid,g.id_):
                        await state(c,uid,g.id_)
        response=await gachas_get_available_gachas(request)
        from scripts._sirius import _unpack_all,_decompress
        parts=[_decompress(x) for x in _unpack_all(response.body)]
        parts[2]=await build_present(app,uid,'GachaReRoll')
        from fastapi.responses import Response
        return Response(b''.join(msgpack.packb(x,use_bin_type=True) for x in parts),media_type='application/vnd.msgpack')

    async def run(request, detail_id, action):
        uid=current_user_id(request);g,d=detail_of(detail_id)
        error=BooleanResult(is_success=False) if action=='decide' else GachaRollResult()
        if uid is None or g is None or int(g.gacha_type)!=9 or g.id_ not in active_gacha_ids():
            return respond(error,faults=[fault('InvalidRequest')])
        body=None
        async with app.acquire_db() as c,c.transaction():
            await c.conn.execute('SELECT pg_advisory_xact_lock($1)',uid)
            row=await c.conn.fetchrow('SELECT * FROM preservation_reroll WHERE user_id=$1 AND banner_id=$2',uid,g.id_)
            old=await c.conn.fetchrow('SELECT * FROM gacha_re_roll WHERE "userId"=$1 AND "gachaMasterId"=$2',uid,g.id_)
            if row and row['detail_id']!=detail_id:
                return respond(error,faults=[fault('InvalidRequest')])
            decided=(row and row['decided']) or (old and old['isDecided'])
            if action=='decide':
                if not decided and row is None: return respond(error,faults=[fault('InvalidRequest')])
                if not decided:
                    pool={t.id_:t for t in g.things};ids=json.loads(row['prizes']);prizes=[pool[i] for i in ids]
                    await award(c,uid,g,d,prizes)
                    await c.execute(add_gacha_rolls(uid,g.id_,len(prizes),_random_gacha_id()))
                    await c.execute(add_gacha_historys(uid,int(g.card_type),[t.thing_id for t in prizes],int(time.time()*1e6)))
                    await c.conn.execute('UPDATE preservation_reroll SET decided=true WHERE user_id=$1 AND banner_id=$2',uid,g.id_)
                    await state(c,uid,g.id_,row['roll_count'],True)
            elif action=='get' or (action=='start' and row):
                if row is None: return respond(error,faults=[fault('InvalidRequest')])
                body=bytes(row['preview'])
            else:
                if decided: return respond(error,faults=[fault('InvalidRequest')])
                count=row['roll_count'] if row else 0
                # Limit interpreted as number of rerolls after initial draw; null unlimited.
                if row and g.re_roll_limit is not None and count-1>=g.re_roll_limit:
                    return respond(error,faults=[fault('InvalidRequest')])
                if row is None and await _spend_cost(c,uid,d) is None:
                    return respond(error,faults=[fault('NotEnoughThing')])
                prizes=roll_prizes(g,d)
                if len(prizes)!=(d.prize_count or 0): raise RuntimeError('Incomplete reroll pool')
                # Reuse duplicate/reward formatting in a rolled-back savepoint. No
                # inventory grant survives the preview; confirmation grants once.
                tx=c.transaction();await tx.start()
                try: body=bytes(respond(await award(c,uid,g,d,prizes)).body)
                finally: await tx.rollback()
                await c.conn.execute('INSERT INTO preservation_reroll VALUES ($1,$2,$3,$4,$5,$6,false) ON CONFLICT (user_id,banner_id) DO UPDATE SET prizes=$4,preview=$5,roll_count=$6',uid,g.id_,detail_id,json.dumps([t.id_ for t in prizes]),body,count+1)
                await state(c,uid,g.id_,count+1,False)
        present=await build_present(app,uid,'GachaReRoll','Item','Currency','Character','Poster','Gacha')
        if action=='decide':return respond(BooleanResult(is_success=True),present=present)
        from scripts._sirius import _unpack_all,_decompress
        from fastapi.responses import Response
        parts=[_decompress(x) for x in _unpack_all(body)];parts[2]=present
        return Response(b''.join(msgpack.packb(x,use_bin_type=True) for x in parts),media_type='application/vnd.msgpack')

    @router.post('/api/Gachas/Roll/{gachaDetailMasterId}')
    async def start(request:Request,gachaDetailMasterId:int):
        g,_=detail_of(gachaDetailMasterId)
        if g is not None and int(g.gacha_type)==9:return await run(request,gachaDetailMasterId,'start')
        return await gachas_roll_gacha(request,gachaDetailMasterId)
    # Actual 2.31.3 client URL; retain the inferred old name as an alias.
    @router.post('/api/Gachas/ReRoll')
    @router.post('/api/Gachas/ReRollGacha')
    async def reroll(request:Request,gachaDetailMasterId:int):return await run(request,gachaDetailMasterId,'reroll')
    @router.post('/api/Gachas/GetReRollGachaResults')
    async def get(request:Request,gachaDetailMasterId:int):return await run(request,gachaDetailMasterId,'get')
    @router.post('/api/Gachas/DecideReRollGacha')
    async def decide(request:Request,gachaDetailMasterId:int):return await run(request,gachaDetailMasterId,'decide')
    app.router.routes[0:0]=router.routes
