"""Lesson/course lifecycles and rank/daily accounting. See preservation-rules.json.

Unknown limits are not enforced. Lesson star points and rank XP per stamina are
explicit preservation policy, not a claimed reverse engineering of all modifiers.
"""
import json,math,random,time
from pathlib import Path
from fastapi import APIRouter,Request
from gameplay import State,Rejected,master,transaction,mission_progress,character_progress
from helpers.cache import cache
from helpers.msgpack import respond,read_request,fault
from helpers.daily import most_recent_reset
from helpers.live import build_live_unit
from helpers.live_result import achievement_rate,play_totals,clear_lamp
from helpers.stamina import max_stamina,adjust_and_check_stamina
from models import (BooleanResult,StartLessonPayload,StartLivePayload,SetLessonPartyPayload,
                    LiveUnit,LessonResult,StarPointResult,PlayerRankPointResult)
from db.user import create_active_live,delete_active_lives
ROOT=Path(__file__).resolve().parents[1]
router=APIRouter()

def rules():
    return json.loads((ROOT/'preservation-rules.json').read_text())

async def daily(s,now=None):
    now=now if now is not None else time.time_ns()//1000
    row=await s.one('DailyLimit')
    zero=dict(autoPlayTimes=0,dailyLessonTimes=0,musicCourseFreeChallengeTimes=0,lastRefreshedAt=now)
    if not row:return await s.insert('DailyLimit',**zero)
    if (row['lastRefreshedAt'] or 0)<most_recent_reset(now):await s.update('DailyLimit',row,**zero)
    return row

async def use_daily(s,field):
    row=await daily(s)
    if not rules()['unlimited_attempts']:await s.update('DailyLimit',row,**{field:row[field]+1})

async def refresh_daily(app,uid):
    if uid is None:return
    async with app.acquire_db() as conn,conn.transaction():
        await conn.conn.execute('SELECT pg_advisory_xact_lock($1)',uid)
        await daily(State(conn,uid))

async def context(s,mode,ident,extra):
    await s.conn.conn.execute('DELETE FROM preservation_live_context WHERE "userId"=$1',s.uid)
    await s.conn.conn.execute('INSERT INTO preservation_live_context ("userId",mode,"masterId",extra) VALUES ($1,$2,$3,$4)',s.uid,mode,ident,extra)

def lesson_slots(row):
    return [(x["position"],x.get("setCharacterId")) if isinstance(x,dict) else tuple(x) for x in row["setCharacters"] or []]

def stored_slots(slots):
    return [dict(position=i,setCharacterId=cid) for i,cid in sorted(slots)]

async def lesson_party(s,base):
    if not await s.one('CharacterBase',characterBaseMasterId=base):raise Rejected('Character not owned')
    row=await s.one('CharacterLesson',characterBaseMasterId=base)
    if row:return row
    owned=[r for r in await s.rows('Character') if master('character_master',r['characterMasterId']).character_base_master_id==base]
    owned.sort(key=lambda c:(c['level'],c['awakeningPhase'],c['id']),reverse=True)
    if not owned:raise Rejected('No lesson actors')
    slots=[[i+1,owned[i]['id'] if i<len(owned) else None] for i in range(5)]
    return await s.insert('CharacterLesson',characterBaseMasterId=base,setCharacters=stored_slots(slots),bestScore=0,leaderPosition=0,rewardReceivedHighScore=0)

@router.post('/api/Lessons/{base}/CreateParty')
async def create_lesson(request:Request,base:int):
    try:
        async with transaction(request) as s:await lesson_party(s,base)
        return respond(BooleanResult(is_success=True),present=s.present())
    except Rejected:return respond(BooleanResult())

@router.post('/api/Lessons/{base}/SetParty')
async def set_lesson(request:Request,base:int):
    try:
        p=await read_request(request,SetLessonPartyPayload)
        if not p or not p.slots:raise Rejected()
        async with transaction(request) as s:
            row=await lesson_party(s,base);slots=[];seen=set();positions=set()
            for x in p.slots:
                if not 1<=x.order<=5 or x.order in positions:raise Rejected()
                positions.add(x.order)
                if x.character_id:
                    c=await s.one('Character',id=x.character_id)
                    if not c or x.character_id in seen or master('character_master',c['characterMasterId']).character_base_master_id!=base:raise Rejected()
                    seen.add(x.character_id)
                slots.append([x.order,x.character_id or None])
            if not seen:raise Rejected()
            slots.extend([i,None] for i in range(1,6) if i not in positions)
            leader=row['leaderPosition']
            if leader and not any(i==leader and cid for i,cid in slots):leader=0
            await s.update('CharacterLesson',row,setCharacters=stored_slots(slots),leaderPosition=leader)
        return respond(BooleanResult(is_success=True),present=s.present())
    except Rejected:return respond(BooleanResult())

@router.post('/api/Lessons/{base}/SetPartyLeader/{position}')
async def set_leader(request:Request,base:int,position:int):
    try:
        async with transaction(request) as s:
            row=await lesson_party(s,base)
            if not 0<=position<=5:raise Rejected()
            if position and not any(i==position and ident for i,ident in lesson_slots(row)):raise Rejected()
            await s.update('CharacterLesson',row,leaderPosition=position)
        return respond(BooleanResult(is_success=True),present=s.present())
    except Rejected:return respond(BooleanResult())

@router.post('/api/Lives/StartLesson')
async def start_lesson(request:Request):
    try:
        p=await read_request(request,StartLessonPayload)
        if p is None:raise Rejected()
        base=p.character_base_master_id;chart=p.live_master_id
        if not master('live_master',chart):raise Rejected('Unknown chart')
        async with transaction(request) as s:
            row=await lesson_party(s,base);await daily(s)
            if not any(cid for _,cid in lesson_slots(row)):raise Rejected('Empty lesson party')
            # Temporary party only exists within this transaction and is removed
            # before return; no phantom party or slot appears in the account.
            party_id=max([r['id'] for r in await s.rows('Party')]+[0])+1
            from db import user as q
            await s.conn.execute(q.upsert_party(s.uid,dict(id=party_id,order=0,name='Lesson',leaderPosition=row['leaderPosition'] or 1)))
            sid=max([r['id'] for r in await s.rows('PartySlot')]+[0])+1
            for position,ident in lesson_slots(row):
                if not ident:continue
                actor=await s.one('Character',id=ident)
                if not actor or master('character_master',actor['characterMasterId']).character_base_master_id!=base:raise Rejected(f'Invalid lesson actor at slot {position}: requested base {base}, actor present {bool(actor)}')
                await s.conn.execute(q.upsert_party_slot(s.uid,dict(id=sid,partyId=party_id,position=position,characterId=ident,posterId=None,accessoryId=None,bonusAbilityEnableFlags=0)))
                sid+=1
            unit,live_id=await build_live_unit(s.conn,s.uid,party_id,chart)
            await s.conn.conn.execute('DELETE FROM party_slot WHERE "userId"=$1 AND "partyId"=$2',s.uid,party_id)
            await s.conn.conn.execute('DELETE FROM party WHERE "userId"=$1 AND id=$2',s.uid,party_id)
            await s.conn.execute(delete_active_lives(s.uid))
            await s.conn.execute(create_active_live(s.uid,live_id,chart,0,1,False))
            await s.conn.conn.execute('DELETE FROM preservation_course_run WHERE "userId"=$1',s.uid)
            await context(s,'lesson',base,{'rank_xp':rules()['lesson_rank_xp']})
        return respond(unit,present=s.present())
    except Rejected as e:return respond(None,faults=[fault('InvalidLesson',str(e))])

async def star_points(s,base,points):
    row=await s.one('CharacterBase',characterBaseMasterId=base)
    if not row:raise Rejected()
    before=row['starRank'];rank=before;old=row['totalStarPoint'];balance=old+points
    while True:
        m=master('character_star_rank_master',rank,'rank')
        if not m or m.next_rank_point<=0 or balance<m.next_rank_point or not master('character_star_rank_master',rank+1,'rank'):break
        balance-=m.next_rank_point;rank+=1
    await s.update('CharacterBase',row,starRank=rank,totalStarPoint=balance)
    things=[]
    for r in cache.star_rank_reward_master:
        if r.character_base_master_id==base and before<r.rank<=rank:
            group=master('character_star_rank_reward_group_master',r.character_star_rank_reward_group_master_id)
            things.extend((int(x.thing_type),x.thing_id,x.thing_quantity) for x in group.rewards or [])
    received=await s.grant(things)
    return StarPointResult(rank_before=before,rank_after=rank,star_point_before=old,star_point_after=balance,star_point_acquired=points,received_reward=received)

async def rank_xp(s,amount):
    row=await s.one('User');before=row['playerRank'];old=row['currentRankPoint'];stamina=row['currentStamina']
    rank=before;balance=old+amount
    levels={x.rank:x for x in cache.player_rank_master}
    cap=min(row['playerRankLimit'],max(x.rank for x in cache.player_rank_master if x.is_released_rank))
    restore=0
    while rank<cap:
        m=levels.get(rank)
        if not m or m.point_to_level_up<=0 or balance<m.point_to_level_up or rank+1 not in levels:break
        balance-=m.point_to_level_up;rank+=1;restore+=max_stamina(rank)
    await s.update('User',row,playerRank=rank,currentRankPoint=balance)
    if restore:
        await adjust_and_check_stamina(s.conn,s.uid,restore,rank)
        s.tables.pop('User',None);row=await s.one('User');s.dirty[('User',row['id'])]=row.copy()
    if rank!=before:
        for ident in (1000,1100):await mission_progress(s,ident,absolute=rank)
    return PlayerRankPointResult(rank_before=before,rank_after=rank,rank_point_before=old,rank_point_after=balance,rank_point_acquired=amount,stamina_before=stamina)

async def finish_lesson(s,base,p,result):
    row=await lesson_party(s,base);score,cleared=play_totals(p);before=row['bestScore']
    things=[]
    for threshold in cache.character_lesson_score_reward_master:
        if threshold.character_base_master_id==base and row['rewardReceivedHighScore']<threshold.required_score<=score:
            group=master('lesson_score_reward_group_master',threshold.lesson_score_group_master_id)
            things.extend((int(x.thing_type),x.thing_id,x.thing_quantity) for x in group.rewards or [])
    received=await s.grant(things)
    await s.update('CharacterLesson',row,bestScore=max(before,score),rewardReceivedHighScore=max(row['rewardReceivedHighScore'],score))
    await use_daily(s,'dailyLessonTimes')
    # Generous fallback expressly authorized by the user; not an exact formula.
    points=rules()['lesson_star_points'] if cleared else 0
    star=await star_points(s,base,points)
    for ident in {base}|{master('character_master',a['characterMasterId']).secondary_character_base_master_id for a in await s.rows('Character') if any(a['id']==cid for _,cid in lesson_slots(row))}:
        if ident:await character_progress(s,ident,1,1)
    await mission_progress(s,100200,create=True)
    result.lesson_result=LessonResult(character_base_master_id=base,star_point_result=star,high_score_rewards=received,high_score_before=before,high_score_after=max(before,score))

@router.post('/api/CharacterMissions/{base}/receiveKeyMission')
async def key_mission(request:Request,base:int):
    try:
        async with transaction(request) as s:
            row=await s.one('CharacterBase',characterBaseMasterId=base)
            if not row:raise Rejected()
            m=master('character_key_mission_master',row['keyMissionLevel']+1,'level')
            if not m:raise Rejected()
            counts={r['characterMissionMasterId']:r['currentCount'] for r in await s.rows('CharacterMission') if r['characterBaseMasterId']==base}
            categories={x.id_ for x in cache.character_mission_category_level_master if x.level==m.level}
            complete=0
            for category in categories:
                goals=[(x.id_,st.goal_count) for x in cache.character_mission_master for st in x.stages or [] if st.character_mission_category_level_master_id==category]
                if goals and all(counts.get(ident,0)>=goal for ident,goal in goals):complete+=1
            if complete<m.required_category_count:raise Rejected()
            await s.update('CharacterBase',row,keyMissionLevel=m.level)
            result=await star_points(s,base,m.give_star_point)
        return respond(result,present=s.present())
    except Rejected:return respond(StarPointResult())


def find_course(detail_id):
    for m in cache.music_course_master:
        details=sorted(m.details or [],key=lambda d:d.set_list_number)
        for i,d in enumerate(details):
            if d.id_==detail_id:return m,details,i
    raise Rejected('Unknown course stage')

@router.post('/api/Lives/StartMusicCourseLive')
async def start_course(request:Request):
    try:
        p=await read_request(request,StartLivePayload)
        if p is None:raise Rejected()
        course,details,index=find_course(p.music_course_detail_master_id)
        d=details[index]
        if d.live_master_id!=p.live_master_id or int(p.music_course_gauge_type) not in (0,1):raise Rejected('Unsupported course chart')
        async with transaction(request) as s:
            old=await s.conn.conn.fetchrow('SELECT * FROM preservation_course_run WHERE "userId"=$1',s.uid)
            active=await s.conn.conn.fetchrow('SELECT * FROM preservation_live_context WHERE "userId"=$1',s.uid)
            if active and active['mode']=='course':raise Rejected('Finish or retire the active stage first')
            if index==0:
                usage=await daily(s);policy=rules();paid='unlimited'
                if not policy['unlimited_attempts']:
                    if usage['musicCourseFreeChallengeTimes']<policy['course_free_attempts']:
                        await use_daily(s,'musicCourseFreeChallengeTimes');paid='free'
                    else:
                        item=await s.one('Item',itemMasterId=course.required_item_master_id)
                        amount=course.required_amount
                        if item and item['stock']>=amount and amount>0:
                            await s.pay({course.required_item_master_id:amount});paid='ticket'
                        elif policy['waive_missing_course_tickets']:paid='waived'
                        else:raise Rejected('No course entry remaining')
                data={'course':course.id_,'gauge':int(p.music_course_gauge_type),'next':0,'rates':[],'lamps':[],'payment':paid,'started_at':time.time_ns()//1000}
                await s.conn.conn.execute('DELETE FROM preservation_course_run WHERE "userId"=$1',s.uid)
                await s.conn.conn.execute('INSERT INTO preservation_course_run ("userId",data) VALUES ($1,$2)',s.uid,data)
            else:
                if not old:raise Rejected('Course has not started')
                data=old['data']
                if data['course']!=course.id_ or data['next']!=index or data['gauge']!=int(p.music_course_gauge_type):raise Rejected('Wrong course stage')
                if data['started_at']<most_recent_reset(time.time_ns()//1000):raise Rejected('Course crossed daily reset')
            live_id=random.randint(1_000_000,9_999_999_999)
            await s.conn.execute(delete_active_lives(s.uid))
            await s.conn.execute(create_active_live(s.uid,live_id,p.live_master_id,0,0,False))
            await context(s,'course',d.id_,{})
        return respond(LiveUnit(u_active_live_id=live_id),present=s.present())
    except Rejected as e:return respond(None,faults=[fault('InvalidCourse',str(e))])

async def finish_course(s,ident,p,result):
    course,details,index=find_course(ident)
    run=await s.conn.conn.fetchrow('SELECT * FROM preservation_course_run WHERE "userId"=$1',s.uid)
    if not run or run['data']['next']!=index:raise Rejected('Missing course session')
    data=run['data'];score,cleared=play_totals(p)
    if data['started_at']<most_recent_reset(time.time_ns()//1000):raise Rejected('Course crossed daily reset')
    data['rates'].append(round(achievement_rate(p.base_score_blocks),4))
    data['lamps'].append(int(clear_lamp(cleared,p.base_score_blocks)));data['next']=index+1
    result.player_rank_point_result=None
    if not cleared or index==len(details)-1:
        old=await s.one('MusicCourse',musicCourseMasterId=course.id_)
        grade=(3 if data['gauge']==1 else 2) if cleared and all(data['lamps']) and index==len(details)-1 else 1
        lamp=min(data['lamps']) if grade>1 else 0
        total=round(sum(data['rates']),4)
        beforegrade=old['certificationGrade'] if old else 0
        best=float(old['totalAchievementRatePercentRecord'] or 0) if old else 0
        values=dict(clearLamp=max(old['clearLamp'] if old else 0,lamp),certificationGrade=max(beforegrade,grade),totalAchievementRatePercentRecord=str(max(best,total)))
        if old:await s.update('MusicCourse',old,**values)
        else:await s.insert('MusicCourse',musicCourseMasterId=course.id_,**values)
        # Master rewards apply once when a new certification grade is attained.
        things=[]
        for group in cache.music_course_reward_group_master:
            if group.music_course_master_id==course.id_ and beforegrade<int(group.required_certification_grade)<=grade:
                things.extend((int(x.thing_type),x.thing_id,x.thing_quantity) for x in group.rewards or [])
        await s.grant(things)
        await s.conn.conn.execute('DELETE FROM preservation_course_run WHERE "userId"=$1',s.uid)
    else:await s.conn.conn.execute('UPDATE preservation_course_run SET data=$2 WHERE "userId"=$1',s.uid,data)

async def finish_context(s,context,p,result):
    mode=context['mode'];extra=context['extra'] or {}
    if mode=='course':await finish_course(s,context['masterId'],p,result);return
    if mode=='lesson':await finish_lesson(s,context['masterId'],p,result)
    if extra.get('auto'):await use_daily(s,'autoPlayTimes')
    if extra.get('rank_xp',0)>0:result.player_rank_point_result=await rank_xp(s,extra['rank_xp'])
    score,cleared=play_totals(p)
    await mission_progress(s,1600)
    if cleared:await mission_progress(s,1800)
    await mission_progress(s,3600,len(p.base_score_blocks or []))


def install(app):
    import routes.login,helpers.daily
    routes.login.refresh_daily_limits=refresh_daily
    helpers.daily.refresh_daily_limits=refresh_daily
    n=len(app.router.routes);app.include_router(router)
    app.router.routes[:]=app.router.routes[n:]+app.router.routes[:n]
