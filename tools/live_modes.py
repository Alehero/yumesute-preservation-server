"""Master-driven Anthology and audition progression, serialized with live results."""
from contextlib import asynccontextmanager
from fastapi import APIRouter, Request
from gameplay import State, Rejected, master, transaction
from helpers.cache import cache
from helpers.msgpack import respond, read_request, from_array, fault
from helpers.live import build_live_time_event
from helpers.live_result import play_totals
from helpers.score import verify_score_blocks
from models import StartLivePayload, FinishLivePayload, FinishLiveResult, ConcertResult
from routes import lives as upstream
from scripts._sirius import _unpack_all, _decompress

router = APIRouter()

class BoundApp:
    def __init__(self, app, conn): self.app, self.conn = app, conn
    def __getattr__(self, name): return getattr(self.app, name)
    @asynccontextmanager
    async def acquire_db(self): yield self.conn

async def call_bound(request, s, fn):
    original = request.scope['app']
    request.scope['app'] = BoundApp(original, s.conn)
    try: return await fn(request)
    finally: request.scope['app'] = original

def parts(response):
    return [_decompress(v) for v in _unpack_all(response.body)]

def concert_available(stage, cleared):
    siblings = sorted((m.id_ for m in cache.concert_stage_master if m.concert_master_id == stage.concert_master_id))
    pos = siblings.index(stage.id_)
    return stage.id_ in cleared or pos == 0 or siblings[pos-1] in cleared

def phases(ident):
    return sorted((p for p in cache.audition_phase_master if p.auditionaster_id == ident), key=lambda p:p.phase)

def attained(ident, score, acts, cleared):
    return max([p.phase for p in phases(ident) if cleared and score >= p.clear_score and acts >= (p.star_act_count or 0)] + [0])

def rewards(rows):
    return [(int(r.thing_type), r.thing_id, r.thing_quantity) for r in rows or []]

@router.post('/api/Lives/Start')
@router.post('/api/Lives/StartConcert')
async def start(request: Request):
    try:
        p = await read_request(request, StartLivePayload)
        if p is None: raise Rejected('Missing payload')
        concert = request.url.path.endswith('StartConcert')
        mode, ident = ('concert', p.concert_stage_master_id) if concert else ('audition', p.audition_master_id)
        m = master('concert_stage_master' if concert else 'audition_master', ident) if ident else None
        chart = master('live_master', p.live_master_id)
        if not chart or (concert and not m) or (ident and not m) or (m and chart.music_master_id != m.music_master_id):
            raise Rejected('Invalid stage or chart')
        async with transaction(request) as s:
            if not await s.one('Party', id=p.party_id): raise Rejected('Missing party')
            if concert and not concert_available(m, {r['concertStageMasterId'] for r in await s.rows('ConcertStage')}):
                raise Rejected('Stage is locked')
            from progression import daily, context, rules
            await daily(s)
            r = parts(await call_bound(request, s, upstream.lives_start))
            active = await s.conn.conn.fetchrow('SELECT * FROM active_live WHERE "userId"=$1',s.uid)
            music=master('music_master',chart.music_master_id)
            xp=int(music.stamina_consumption*max(1,p.stamina_consumption_ratio)*rules()['rank_xp_per_stamina']) if active['staminaSpent'] else 0
            await context(s,mode if m else 'normal',ident or 0,{'rank_xp':xp,'auto':p.is_auto_play})
            await s.conn.conn.execute('DELETE FROM preservation_course_run WHERE "userId"=$1',s.uid)
            if m:
                unit = from_array('LiveUnit', r[1])
                lte = await build_live_time_event(s.conn, s.uid, p.party_id, m.music_master_id, m.sense_notation_master_id)
                unit.time_events = {t.timing_seconds:t.event for t in lte.timings}
                r[1] = unit
        return respond(r[1], faults=r[0], present=r[2]+s.present())
    except Rejected as e:
        return respond(None, faults=[fault('InvalidLiveStage', str(e))])

async def apply_progress(s, mode, ident, score, acts, cleared, result):
    m = master('concert_stage_master' if mode == 'concert' else 'audition_master', ident)
    if not m: raise Rejected('Missing stage master')
    if mode == 'concert':
        received = []
        if cleared and score >= m.clear_score and not await s.one('ConcertStage', concertStageMasterId=ident):
            received = await s.grant(rewards(m.rewards))
            await s.insert('ConcertStage', concertStageMasterId=ident)
        result.concert_result = ConcertResult(rewards=received)
        return
    row = await s.one('AuditionClear', auditionMasterId=ident)
    before = max(row['clearPhase'], row['skipClearPhase']) if row else 0
    achieved = min(before + 1, attained(ident, score, acts, cleared))
    result.audition_master_id = ident
    result.audition_before_phase = before
    result.audition_after_phase = max(before, achieved)
    things = []
    # The official challenge clear awards the stages in their master order.
    targets = sorted((x for x in cache.audition_master if x.audition_group_number == m.audition_group_number and x.id_ <= ident), key=lambda x:x.id_)
    for target in targets:
        target_phases = phases(target.id_)
        new = min(achieved, max([p.phase for p in target_phases]+[0]))
        if not new: continue
        existing = await s.one('AuditionClear', auditionMasterId=target.id_)
        old = max(existing['clearPhase'], existing['skipClearPhase']) if existing else 0
        if new <= old: continue
        for phase in target_phases:
            if old < phase.phase <= new:
                package = master('audition_reward_package_master', phase.audition_reward_package_master_id)
                if not package: raise Rejected('Missing reward package')
                things.extend(rewards(package.rewards))
        field = 'clearPhase' if target.id_ == ident else 'skipClearPhase'
        if existing:
            if new > existing[field]: await s.update('AuditionClear', existing, **{field:new})
        else:
            values = dict(auditionMasterId=target.id_, clearPhase=0, skipClearPhase=0, auditionClearPartyId=0)
            values[field] = new
            await s.insert('AuditionClear', **values)
    # Preserve reward entries in their official order (including repeated item types).
    result.audition_rewards = []
    for thing in sorted(things, key=lambda t:t[0]):
        result.audition_rewards.extend(await s.grant([thing]))

@router.post('/api/Lives/FinishAndValidate')
async def finish(request: Request):
    try:
        p = await read_request(request, FinishLivePayload)
        if p is None or not verify_score_blocks(p): raise Rejected('Invalid score blocks')
        async with transaction(request) as s:
            active = await s.conn.conn.fetchrow('SELECT * FROM active_live WHERE "userId"=$1', s.uid)
            if not active: raise Rejected('No active live')
            context = await s.conn.conn.fetchrow('SELECT * FROM preservation_live_context WHERE "userId"=$1', s.uid)
            r = parts(await call_bound(request, s, upstream.lives_finish_and_validate))
            if r[0]: raise Rejected('Live validation failed')
            result = from_array('FinishLiveResult', r[1])
            if context:
                score, cleared = play_totals(p)
                if context['mode'] in ('concert','audition'):
                    await apply_progress(s, context['mode'], context['masterId'], score, len(p.star_act_score_blocks or []), cleared, result)
                from progression import finish_context
                await finish_context(s,context,p,result)
            await s.conn.conn.execute('DELETE FROM preservation_live_context WHERE "userId"=$1', s.uid)
            changed = s.present()
            keys = {(v[0],v[1][0]) for v in changed}
            present = [v for v in r[2] if (v[0],v[1][0]) not in keys] + changed
        return respond(result, present=present)
    except Rejected as e:
        return respond(FinishLiveResult(), faults=[fault('InvalidLiveState', str(e))])

@router.post('/api/Lives/Retire')
async def retire(request: Request):
    async with transaction(request) as s:
        await s.conn.conn.execute('DELETE FROM preservation_live_context WHERE "userId"=$1', s.uid)
        await s.conn.conn.execute('DELETE FROM preservation_course_run WHERE "userId"=$1',s.uid)
        return await call_bound(request, s, upstream.lives_retire)

def install(app):
    previous = app.router.lifespan_context
    @asynccontextmanager
    async def lifespan(app):
        async with previous(app):
            from scoring_compat import repair_character_stats
            repair_character_stats()
            from preservation_dates import repair_cached_dates
            repair_cached_dates()
            async with app.acquire_db() as conn:
                await conn.conn.execute('CREATE TABLE IF NOT EXISTS preservation_live_context ("userId" bigint PRIMARY KEY REFERENCES accounts("userId") ON DELETE CASCADE, mode text NOT NULL, "masterId" integer NOT NULL)')
                await conn.conn.execute("ALTER TABLE preservation_live_context ADD COLUMN IF NOT EXISTS extra jsonb NOT NULL DEFAULT '{}'::jsonb")
                await conn.conn.execute('CREATE TABLE IF NOT EXISTS preservation_course_run ("userId" bigint PRIMARY KEY REFERENCES accounts("userId") ON DELETE CASCADE, data jsonb NOT NULL)')
            yield
    app.router.lifespan_context = lifespan
    count = len(app.router.routes)
    app.include_router(router)
    app.router.routes[:] = app.router.routes[count:] + app.router.routes[:count]
