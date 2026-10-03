"""Release adapter; personal diagnostics and iPhone v3 experiments are excluded."""
import hashlib
import hmac
import json
import os
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT/'vendor/server-of-dreams'))
from app import app
from gameplay import install
install(app)
from live_drop_windows import install as install_drop_windows
install_drop_windows()
from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, Response
from helpers.auth import make_session_jwt, make_jwt
from helpers.msgpack import read_request, respond, fault
from helpers.user_data import user_data as database_user_data
from helpers.mastermemory import from_json
from db.account import get_account_by_id, update_account_token
from models import AuthenticateResult, MasterDataManifest, TakeOverAccountPayload, TakeOverAccountResult
from scripts._sirius import _unpack_all, _decompress
from preservation_dates import preserved_master
from account_compat import merge_account
from circle_compat import install as install_circle_compat
from starter_login import register_starter, authenticate_starter
import routes.account
import routes.data
ACCOUNT = json.loads((ROOT/'private/account.json').read_text())
from official_recovery import Recovery, RecoveryError, Rejected
RECOVERY = Recovery(app, ACCOUNT)

@app.exception_handler(RecoveryError)
async def recovery_failure(request, exc):
    return respond(None, faults=exc.faults or [fault(exc.code, 'Account recovery could not complete. Your local saves are unchanged.')])

def manifest():
    data=json.loads((ROOT/'private/upstream/master-manifest.json').read_text())
    _,digest,_=preserved_master()
    version=f'1790658001_{int(digest[:8],16)}'
    data.update(uri=f'preservation/mastermemory_{version}.db', version=version,
                publish_timestamp=1790658001, sas_token='')
    return MasterDataManifest(**data)

async def authenticate(payload, app):
    starter = await authenticate_starter(payload, app, ACCOUNT)
    if starter is not None: return starter
    if payload and payload.login_token:
        known=await RECOVERY.local_token_uid(payload.login_token)
        if known is not None:
            return AuthenticateResult(token=await RECOVERY.session(known),ban_level=0)
    expected=ACCOUNT.get('token_sha256')
    if expected and payload and hmac.compare_digest(hashlib.sha256((payload.login_token or '').encode()).hexdigest(), expected):
        async with app.acquire_db() as conn:
            row=await conn.fetchrow(get_account_by_id(ACCOUNT['user_id']))
            if row:
                token=make_session_jwt(ACCOUNT['user_id'],'AppStore')
                await conn.execute(update_account_token(ACCOUNT['user_id'],token))
                return AuthenticateResult(token=token,ban_level=row.banLevel)
            raise RecoveryError('LocalAccountMissing')
    if not payload or not payload.login_token:
        return AuthenticateResult(token='', ban_level=0)
    uid = await RECOVERY.resolve(auth=payload)
    return AuthenticateResult(token=await RECOVERY.session(uid), ban_level=0)

async def user_data(app,uid):
    from preservation_gift import ensure_gift
    await ensure_gift(app, uid)
    from starter_music import ensure_starter_music
    await ensure_starter_music(app, uid, ACCOUNT)
    current=await database_user_data(app,uid)
    current=await RECOVERY.merge(uid,current)
    if uid != ACCOUNT['user_id'] or ACCOUNT['mode']!='import': return current
    raw=(ROOT/'private/account-snapshot/user-data.response.bin').read_bytes()
    original=[_decompress(x) for x in _unpack_all(raw)][1]
    baseline=from_json(json.loads((ROOT/'private/imported-user-roundtrip.json').read_text()))
    return merge_account(original,baseline,current)

routes.account.authenticate=authenticate
routes.data.user_data=user_data
routes.data.master_data_manifest=manifest
router=APIRouter()

@router.post('/api/Account/GetTakeOverAccount')
async def transfer(request:Request):
    p=await read_request(request,TakeOverAccountPayload)
    if not p or not p.password or len(p.password)>16: return respond(TakeOverAccountResult(is_success=False))
    t=ACCOUNT['transfer']
    digest=hashlib.scrypt(p.password.encode(),salt=t['salt'].encode(),n=16384,r=8,p=1).hex()
    if hmac.compare_digest(p.linkage_code or '',t['code']) and hmac.compare_digest(digest,t['hash']):
        uid=ACCOUNT['user_id']
    else:
        if hmac.compare_digest(p.linkage_code or '', t['code']):
            return respond(TakeOverAccountResult(is_success=False))
        try:
            uid=await RECOVERY.resolve(transfer=p)
        except Rejected as exc:
            return respond(TakeOverAccountResult(is_success=False), faults=exc.faults)
    async with app.acquire_db() as conn:
        row=await conn.conn.fetchrow('SELECT u."hashUserId",u."playerRank",p.name FROM "user" u JOIN user_profile p ON p."userId"=u."userId" WHERE u."userId"=$1',uid)
    if not row: raise RecoveryError('LocalAccountMissing')
    return respond(TakeOverAccountResult(is_success=True,user_id=row['hashUserId'],name=row['name'],rank=row['playerRank'],login_token=make_jwt(uid)))

@router.post('/api/Account/Register')
async def register_local_starter(request:Request):
    # Reuse this installation's fresh save; never reset it or expose an import.
    from models import RegisterPayload
    payload = await read_request(request, RegisterPayload)
    return respond(await register_starter(request.app, ACCOUNT, getattr(payload, 'name', None)))

app.router.routes[0:0]=router.routes
install_circle_compat(app)
from reroll import install as install_reroll
install_reroll(app)
from preservation_gift import install as install_gift
install_gift(app)

@app.middleware('http')
async def local_files(request,call_next):
    path=request.url.path
    if path == '/master-data/production/help.bin':
        help_file=ROOT/'private/upstream/help.bin'
        if help_file.is_file():return FileResponse(help_file,media_type='application/octet-stream')
        return Response('Help metadata not available locally',404)
    if path.startswith('/master-data/production/scenes/'):
        root=(ROOT/'private/upstream/scenes').resolve()
        f=(root/path.rsplit('/',1)[-1]).resolve()
        if root in f.parents and f.is_file(): return FileResponse(f,media_type='application/octet-stream')
        from routes.episodes import episodes_scene_bin
        try: return await episodes_scene_bin(request,path.rsplit('/',1)[-1])
        except Exception: return Response('Scene not available locally',404)
    if path.startswith('/master-data/production/') and path.endswith('.db'):
        return Response(preserved_master()[0],media_type='application/octet-stream')
    if path.startswith('/production/static-assets/'):
        root=(ROOT/'private/static-assets').resolve(); f=(root/path.lstrip('/')).resolve()
        if root in f.parents and f.is_file(): return FileResponse(f,media_type='application/octet-stream')
        return Response(status_code=404)
    response=await call_next(request)
    if path.startswith('/production/') and 300<=response.status_code<400:
        return Response('Asset not available locally',404)
    response.headers['X-Yumesute-Backend']='local-preservation'
    return response

from recovery_page import install as install_recovery_page
install_recovery_page(app,RECOVERY,ROOT,int(os.environ.get('YUMESUTE_PORT','8125')))

if __name__=='__main__':
    import uvicorn
    uvicorn.run(app,host='127.0.0.1',port=int(os.environ.get('YUMESUTE_PORT','8125')))
