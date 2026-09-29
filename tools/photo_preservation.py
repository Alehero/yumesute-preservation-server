"""Persist captured photo/album APIs; film rarity odds remain a documented approximation."""
from pathlib import Path
import time, uuid, io
import msgpack
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import FileResponse
from gameplay import transaction, Rejected, master, mission_progress, character_progress
from helpers.msgpack import respond, read_request, fault
from models import BooleanResult, GeneratePhotoResult
from scripts._sirius import _decompress

ROOT = Path(__file__).resolve().parents[1]
PHOTO_ROOT = ROOT/'private/photo-assets'
router = APIRouter()

async def watch(request, entity, field, ident, valid):
    try:
        if not ident or not valid: raise Rejected('Unknown performance')
        async with transaction(request) as s:
            row=await s.one(entity,**{field:ident})
            if row: await s.update(entity,row,**{field:ident})
            else: await s.insert(entity,**{field:ident})
        return respond(BooleanResult(is_success=True),present=s.present())
    except Rejected:
        return respond(BooleanResult())

@router.post('/api/Photo/WatchMusicVideo')
async def watch_music_video(request: Request, mMusicVideoId: int = 0):
    return await watch(request,'MusicVideo','musicVideoMasterId',mMusicVideoId,master('music_video_master',mMusicVideoId))

@router.post('/api/Photo/WatchTheaterStory')
async def watch_theater_story(request: Request, mTheaterStoryId: int = 0):
    from helpers.cache import cache
    valid=any(story.id_==mTheaterStoryId for chapter in cache.theater_chapter_master for story in chapter.stories or [])
    return await watch(request,'TheaterStory','theaterStoryMasterId',mTheaterStoryId,valid)

def film_rarity(film):
    # Exact server lottery weights were not exposed in master data. Preserve the
    # documented minimum tier; do not invent rare signatures or abilities.
    if film not in range(510001,510007): raise Rejected('Unsupported film')
    return min(film-510000,5)

def jpeg(data):
    if not isinstance(data,bytes) or not 4 <= len(data) <= 12_000_000 or not data.startswith(b'\xff\xd8'):
        raise Rejected('Invalid photo image')
    from PIL import Image
    try:
        with Image.open(io.BytesIO(data)) as im:
            if im.format != 'JPEG' or im.width*im.height > 40_000_000: raise Rejected('Invalid dimensions')
            im.verify()
    except (OSError,ValueError) as e: raise Rejected('Invalid JPEG') from e
    return data

@router.get('/photo/{variant}/{filename}')
async def image(variant: str, filename: str):
    if variant not in ('original','thumbnail') or not filename.endswith('.jpg'):
        raise HTTPException(404)
    try: uuid.UUID(filename[:-4])
    except ValueError: raise HTTPException(404)
    path=PHOTO_ROOT/variant/filename
    if not path.is_file(): raise HTTPException(404)
    return FileResponse(path, media_type='image/jpeg')

@router.post('/api/Photos/GeneratePhoto')
async def generate(request: Request):
    saved=[]
    try:
        p=await read_request(request)
        if not isinstance(p,list) or len(p)!=5 or p[0] is not None: raise Rejected('Unsupported photo request')
        rarity=film_rarity(p[1])
        original,thumbnail=jpeg(p[2]),jpeg(p[3])
        if not isinstance(p[4],list) or len(p[4])>30: raise Rejected('Invalid characters')
        chars=list(dict.fromkeys(c[0] for c in p[4] if isinstance(c,list) and len(c)==2))
        if len(chars)!=len(p[4]) or any(not master('character_base_master',c) for c in chars): raise Rejected('Invalid character')
        name=str(uuid.uuid4())+'.jpg'
        async with transaction(request) as s:
            await s.pay({p[1]:1})
            for variant,data in [('original',original),('thumbnail',thumbnail)]:
                path=PHOTO_ROOT/variant/name
                path.parent.mkdir(parents=True,exist_ok=True)
                with path.open('xb') as f: f.write(data)
                saved.append(path)
            row=await s.insert('Photo', fileName=name,sasToken='',photoEffectMasterId=None,lock=False,useAlbumPage=None,level=1,rarity=rarity,signMasterId=None,generatedAt=time.time_ns()//1000,thumbnailSasToken='',appearedCharacterBaseMasterIds=chars,taggedCharacterBaseMasterIds=chars,useDecoPage=0)
            for ident in (200300,10): await mission_progress(s,ident,create=True)
            for c in chars: await character_progress(s,c,9,1)
        return respond(GeneratePhotoResult(photo_id=row['id'],file_name=name,sas_token='',rarity=rarity),present=s.present())
    except Rejected as e:
        for path in saved: path.unlink(missing_ok=True)
        return respond(GeneratePhotoResult(),faults=[fault('InvalidPhoto',str(e))])
    except BaseException:
        for path in saved: path.unlink(missing_ok=True)
        raise

@router.post('/api/Photos/FinishGeneratePhoto')
async def finish(request: Request):
    async with transaction(request): pass
    return respond(BooleanResult(is_success=True))

def unpack_items(raw):
    try:
        value=_decompress(msgpack.unpackb(bytes(raw),raw=False,strict_map_key=False))
        if not isinstance(value,list) or len(value)!=1 or not isinstance(value[0],list) or len(value[0])>200: raise ValueError()
        return value[0]
    except (ValueError,TypeError,msgpack.UnpackException): raise Rejected('Invalid album layout')

@router.post('/api/Photo/AlbumSimpleArranging')
@router.post('/api/Photo/AlbumDetailArranging')
async def arrange(request: Request):
    try:
        p=await read_request(request)
        if not isinstance(p,list) or len(p)!=4: raise Rejected('Invalid album')
        publishing,page,raw,theme=p
        if not isinstance(page,int) or page not in list(range(1,11))+list(range(101,111)): raise Rejected('Invalid album page')
        detailed=request.url.path.endswith('DetailArranging')
        items=unpack_items(raw)
        async with transaction(request) as s:
            selected=[]
            for item in items:
                if not isinstance(item,list) or len(item)!=(12 if detailed else 5): raise Rejected('Invalid album item')
                kind=item[1] if detailed else 1
                if kind==1:
                    photo=await s.one('Photo',id=item[0])
                    if not photo: raise Rejected('Photo is not owned')
                    if photo['id'] in selected: raise Rejected('Duplicate photo')
                    selected.append(photo['id'])
                    offset=2 if detailed else 1
                    item[offset:offset+2]=[photo['fileName'],photo['sasToken']]
                elif kind==3:
                    if not master('album_theme_master',item[0]): raise Rejected('Unknown theme')
                elif kind==2:
                    decoration=master('decoration_master',item[0])
                    if not decoration or (not decoration.is_default and not await s.one('Decoration',decorationMasterId=item[0])): raise Rejected('Decoration is not owned')
                elif kind==4:
                    stamp=master('stamp_master',item[0])
                    owned={ident for row in await s.rows('Stamp') for ident in (row['stampMasterIds'] or [])}
                    if not stamp or (not stamp.is_default and item[0] not in owned): raise Rejected('Stamp is not owned')
                else: raise Rejected('Unknown album item type')
            if theme is not None and not master('album_theme_master',theme): raise Rejected('Unknown theme')
            if detailed: items.sort(key=lambda x:x[1])
            normal=page<100
            mask=0 if normal else 1<<(page-101)
            for photo in await s.rows('Photo'):
                if normal:
                    if photo['id'] in selected:
                        if photo['useAlbumPage'] not in (None,0,page): raise Rejected('Photo is already in another album page')
                        await s.update('Photo',photo,useAlbumPage=page)
                    elif photo['useAlbumPage']==page: await s.update('Photo',photo,useAlbumPage=None)
                else:
                    flags=photo['useDecoPage']|mask if photo['id'] in selected else photo['useDecoPage']&~mask
                    if flags!=photo['useDecoPage']: await s.update('Photo',photo,useDecoPage=flags)
            values=dict(page=page,editType=2 if detailed else 1,publishing=bool(publishing and normal),items=list(msgpack.packb([items],use_bin_type=True)),albumThemeMasterId=None if detailed else theme)
            row=await s.one('AlbumPage',page=page)
            if row: await s.update('AlbumPage',row,**values)
            else: await s.insert('AlbumPage',**values)
            album=await s.one('Album')
            if not album: album=await s.insert('Album',level=1,publishPageNumber=1,currentPresetOrder=1)
            if selected and album['level']==0:
                await s.update('Album',album,level=1)
            if publishing and normal:
                await s.update('Album',album,publishPageNumber=page)
                for other in await s.rows('AlbumPage'):
                    if other['page']!=page and other['publishing']: await s.update('AlbumPage',other,publishing=False)
            await mission_progress(s,11,1 if selected else 0,create=True)
        return respond(BooleanResult(is_success=True),present=s.present())
    except Rejected as e: return respond(BooleanResult(),faults=[fault('InvalidAlbum',str(e))])

@router.post('/api/Photo/SetCharacterBaseTags')
async def tags(request: Request):
    try:
        p=await read_request(request)
        if not isinstance(p,list) or len(p)!=2 or not isinstance(p[1],list) or len(p[1])>100: raise Rejected()
        if any(not master('character_base_master',c) for c in p[1]): raise Rejected()
        async with transaction(request) as s:
            row=await s.one('Photo',id=p[0])
            if not row: raise Rejected()
            await s.update('Photo',row,taggedCharacterBaseMasterIds=list(dict.fromkeys(p[1])))
        return respond(BooleanResult(is_success=True),present=s.present())
    except Rejected: return respond(BooleanResult())

@router.post('/api/Photo/GetAlbumMainPage')
async def album_main(request: Request, targetUserId: str | None = None):
    async with transaction(request) as s:
        if targetUserId and targetUserId != str(s.uid): return respond([None,False])
        album=await s.one('Album')
        page=await s.one('AlbumPage',page=album['publishPageNumber']) if album else None
        if not page: return respond([None,False])
        return respond([[page['id'],album['id'],album['level'],page['page'],page['editType'],page['publishing'],bytes(page['items'] or []),page['albumThemeMasterId']],True])


def install(app):
    import helpers.user_data as ud
    if not getattr(ud._conv,'photo_binary_fix',False):
        original=ud._conv
        def conv(base,is_array,kind,value):
            if base=='byte' and is_array and value is not None: return bytes(value)
            return original(base,is_array,kind,value)
        conv.photo_binary_fix=True
        ud._conv=conv
    count=len(app.router.routes)
    app.include_router(router)
    app.router.routes[:]=app.router.routes[count:]+app.router.routes[:count]
