"""Account-owned customization, verified against the official September captures."""
from fastapi import APIRouter, Request
from gameplay import transaction, Rejected, master, mission_progress
from helpers.msgpack import respond, read_request
from models import BooleanResult, EditUserProfilePayload, UpdateHomeDisplayPreferencePayload
router=APIRouter()

def camel(name):
    a=name.split('_');return a[0]+''.join(x.title() for x in a[1:])

async def costume_owned(s,base,ident):
    b=master('character_base_master',base)
    c=master('costume_master',ident)
    if not b or not c or not await s.one('CharacterBase',characterBaseMasterId=base): raise Rejected()
    group=master('costume_group_master',c.costume_group_master_id)
    wearable=master('costume_wearable_character_group_master',group.costume_wearable_character_group_master_id) if group else None
    if wearable and base not in (wearable.character_base_master_ids or []): raise Rejected()
    if not c.is_default and b.default_costume_master_id!=ident and not await s.one('Costume',costumeMasterId=ident): raise Rejected()

@router.post('/api/CharacterBases/{base}/SetCostume/{costume}')
async def set_costume(request:Request,base:int,costume:int):
    try:
        async with transaction(request) as s:
            await costume_owned(s,base,costume)
            await s.update('CharacterBase',await s.one('CharacterBase',characterBaseMasterId=base),costumeMasterId=costume)
        return respond(BooleanResult(is_success=True),present=s.present())
    except Rejected:return respond(BooleanResult())

@router.post('/api/Possessions/SetFavorite')
async def favorite_costume(request:Request):
    try:
        p=await read_request(request)
        if not isinstance(p,list) or len(p)!=3:raise Rejected()
        ident,base,enabled=p
        async with transaction(request) as s:
            await costume_owned(s,base,ident)
            row=await s.one('FavoriteCostume',characterBaseMasterId=base)
            favorites=list(row['favoriteCostumeMasterIds'] or []) if row else []
            if enabled and ident not in favorites:favorites.append(ident)
            if not enabled:favorites=[v for v in favorites if v!=ident]
            if row:await s.update('FavoriteCostume',row,favoriteCostumeMasterIds=favorites)
            else:await s.insert('FavoriteCostume',characterBaseMasterId=base,favoriteCostumeMasterIds=favorites)
        return respond(BooleanResult(is_success=True),present=s.present())
    except Rejected:return respond(BooleanResult())

@router.post('/api/Possessions/AddFavoriteStamp/{ident}')
@router.post('/api/Possessions/RemoveFavoriteStamp/{ident}')
async def favorite_stamp(request:Request,ident:int):
    try:
        async with transaction(request) as s:
            row=await s.one('Stamp');m=master('stamp_master',ident)
            if not row or not m or (not m.is_default and ident not in (row['stampMasterIds'] or [])):raise Rejected()
            favorites=list(row['favoriteStampMasterIds'] or [])
            if '/Add' in request.url.path:
                if ident not in favorites:
                    favorites.append(ident)
                    await mission_progress(s,21,create=True)
            else:favorites=[v for v in favorites if v!=ident]
            await s.update('Stamp',row,favoriteStampMasterIds=favorites)
        return respond(BooleanResult(is_success=True),present=s.present())
    except Rejected:return respond(BooleanResult())

@router.post('/api/Characters/Portal/SetCharacter')
async def portrait(request:Request):
    try:
        p=await read_request(request)
        if not isinstance(p,list) or len(p)!=3:raise Rejected()
        base,ident,awakened=p
        async with transaction(request) as s:
            m=master('character_master',ident)
            actor=await s.one('Character',characterMasterId=ident)
            if not m or not actor:raise Rejected()
            await s.update('CharacterBase',await s.one('CharacterBase',characterBaseMasterId=base),portalCharacterId=ident,portalDisplayAwakeningStatus=bool(awakened))
        return respond(BooleanResult(is_success=True),present=s.present())
    except Rejected:return respond(BooleanResult())

@router.post('/api/Player/UpdateHomeDisplayPreference')
async def home(request:Request):
    try:
        p=await read_request(request,UpdateHomeDisplayPreferencePayload)
        if p is None:raise Rejected()
        values={camel(k):v for k,v in p.model_dump().items()}
        values['loginBonusCostumeMasterId']=values.pop('loginBonusSpineCostumeMasterId')
        async with transaction(request) as s:
            for prefix in ('home','member','story','shop','loginBonus'):
                base=values[prefix+'CharacterBaseMasterId'];costume=values[prefix+'CostumeMasterId']
                if base and not await s.one('CharacterBase',characterBaseMasterId=base):raise Rejected()
                # Login bonus uses spine costume IDs, a different master namespace.
                if base and costume and prefix!='loginBonus':await costume_owned(s,base,costume)
            if values['illustCharacterMasterId'] and not await s.one('Character',characterMasterId=values['illustCharacterMasterId']):raise Rejected()
            row=await s.one('HomeDisplayPreference')
            if row:await s.update('HomeDisplayPreference',row,**values)
            else:await s.insert('HomeDisplayPreference',**values)
        return respond(BooleanResult(is_success=True),present=s.present())
    except Rejected:return respond(BooleanResult())

@router.post('/api/Player/SetHomeBGM')
async def bgm(request:Request,mHomeBGMId:int,selectionType:int,mHomeBGMDetailId:int|None=None):
    try:
        mHomeBGMDetailId=mHomeBGMDetailId or None
        m=master('home_b_g_m_master',mHomeBGMId)
        detail=master('home_b_g_m_detail_master',mHomeBGMDetailId) if mHomeBGMDetailId else None
        if not m or selectionType not in (0,1,2) or (mHomeBGMDetailId and (not detail or detail.home_bgm_master_id!=mHomeBGMId)):raise Rejected()
        async with transaction(request) as s:
            values=dict(selectionType=selectionType,homeBGMDetailMasterId=mHomeBGMDetailId)
            row=await s.one('HomeBGM',homeBGMMasterId=mHomeBGMId)
            if row:await s.update('HomeBGM',row,**values)
            else:await s.insert('HomeBGM',homeBGMMasterId=mHomeBGMId,**values)
        return respond(BooleanResult(is_success=True),present=s.present())
    except Rejected:return respond(BooleanResult())

@router.post('/api/Profiles/Edit')
async def profile(request:Request):
    try:
        p=await read_request(request,EditUserProfilePayload)
        if p is None:raise Rejected()
        values={camel(k):v for k,v in p.model_dump().items()}
        values['nameBaseColorMasterId']=values.pop('nameBaseColorMasterid')
        async with transaction(request) as s:
            row=await s.one('UserProfile')
            if not row:raise Rejected()
            actor=await s.one('Character',id=p.main_u_character_id) if p.main_u_character_id else await s.one('Character',characterMasterId=p.main_character_master_id)
            if not actor or actor['characterMasterId']!=p.main_character_master_id:raise Rejected()
            if p.name is not None and len(p.name)>100:raise Rejected()
            if p.introduction is not None and len(p.introduction)>1000:raise Rejected()
            if values['introduction']!=row['introduction']:
                await mission_progress(s,28,create=True)
            if any(values[k]!=row[k] for k in ('mTrophyId1','mTrophyId2','mTrophyId3')):
                await mission_progress(s,27,create=True)
            await s.update('UserProfile',row,**values)
        return respond(BooleanResult(is_success=True),present=s.present())
    except Rejected:return respond(BooleanResult())

def install(app):
    n=len(app.router.routes);app.include_router(router)
    app.router.routes[:]=app.router.routes[n:]+app.router.routes[:n]
