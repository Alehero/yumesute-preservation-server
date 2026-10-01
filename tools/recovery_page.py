"""Same-origin, loopback-only recovery UI. Downloads never change local saves."""
import asyncio
import hashlib
import hmac
import json
import secrets
import time
from pathlib import Path
from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from models import TakeOverAccountPayload
from exporter import save_snapshot
from official_recovery import RecoveryError, Unavailable, Rejected, credential_key


def install(app, recovery, root, port):
    csrf = secrets.token_urlsafe(32)
    staged = {}
    lock = asyncio.Lock()
    hosts = {f'127.0.0.1:{port}', f'localhost:{port}'}
    headers = {'Cache-Control':'no-store', 'Referrer-Policy':'no-referrer',
               'X-Content-Type-Options':'nosniff', 'X-Frame-Options':'DENY'}

    def allowed(request, write=False):
        host=request.headers.get('host','')
        if host not in hosts or not request.client or request.client.host not in ('127.0.0.1','::1','testclient'):
            return False
        if write:
            return (request.headers.get('origin') == 'http://'+host and
                    hmac.compare_digest(request.headers.get('x-recovery-token',''),csrf))
        return request.headers.get('sec-fetch-site') != 'cross-site'

    def clean():
        for key in list(staged):
            if staged[key]['expires'] < time.monotonic():del staged[key]

    def error(exc):
        if isinstance(exc,(Unavailable,TimeoutError)):
            message='公式に接続できません。セーブは変更していません。 / Official service unavailable; no save changed.'
        elif isinstance(exc,Rejected):
            message='連携情報を確認してください。 / Check your official linking ID and password.'
        else:
            message='復元を完了できませんでした。既存セーブは保持されています。 / Recovery failed; existing saves are preserved.'
        return JSONResponse({'error':message},status_code=400,headers=headers)

    @app.get('/recovery',response_class=HTMLResponse)
    async def page(request:Request):
        if not allowed(request):return JSONResponse({'error':'Open this page on the server computer using localhost.'},403)
        html=(Path(__file__).with_name('recovery_page.html')).read_text().replace('__CSRF__',csrf)
        return HTMLResponse(html,headers={**headers,'Content-Security-Policy':"default-src 'none'; script-src 'nonce-"+csrf+"'; style-src 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"})

    @app.post('/recovery/export')
    async def export(request:Request):
        if not allowed(request,True):return JSONResponse({'error':'Forbidden'},403)
        if lock.locked():return JSONResponse({'error':'A recovery is already running. Please wait.'},409,headers=headers)
        body=await request.body()
        if len(body)>4096:return JSONResponse({'error':'Invalid input'},400,headers=headers)
        try:
            data=json.loads(body)
            code,password=data.get('code'),data.get('password')
            if not isinstance(code,str) or not 1<=len(code)<=128 or not isinstance(password,str) or not 8<=len(password)<=16:
                raise ValueError()
            if hmac.compare_digest(code.encode(),recovery.account['transfer']['code'].encode()):
                return JSONResponse({'error':'Use your official credentials, not this server’s local linking ID.'},400,headers=headers)
            transfer=TakeOverAccountPayload(linkage_code=code,password=password)
        except (ValueError,TypeError,AttributeError):return JSONResponse({'error':'Check the ID and 8–16 character password.'},400,headers=headers)
        try:
            async with lock:
                # Explicit official retry: deliberately bypass local credential lookup; no fallback.
                raw,token=await recovery.official.recover(transfer=transfer)
                archive,manifest=save_snapshot(root/'private/recovered-exports',raw,
                    login_hash=hashlib.sha256(token.encode()).hexdigest(),source='official-api-authenticated-recovery')
                clean()
                if len(staged)>=8:del staged[next(iter(staged))]
                stage=secrets.token_urlsafe(32)
                staged[stage]={'expires':time.monotonic()+900,'raw':raw,
                    'keys':[credential_key('transfer',[code,password]),credential_key('token',token)]}
            return FileResponse(archive,media_type='application/zip',filename=archive.name,
                headers={**headers,'X-Recovery-Stage':stage,'X-Recovery-Records':str(manifest['entries'])})
        except (RecoveryError,TimeoutError) as exc:return error(exc)
        except Exception:return error(RecoveryError())

    @app.post('/recovery/import')
    async def import_save(request:Request):
        if not allowed(request,True):return JSONResponse({'error':'Forbidden'},403)
        body=await request.body()
        if len(body)>4096:return JSONResponse({'error':'Invalid input'},400,headers=headers)
        try:
            data=json.loads(body);clean()
            stage=data.get('stage');entry=staged.get(stage) if isinstance(stage,str) else None
            if not entry or data.get('confirm') is not True:raise ValueError()
        except (ValueError,TypeError,AttributeError):return JSONResponse({'error':'Download again; this recovery expired or was not confirmed.'},400,headers=headers)
        try:
            await recovery.setup()
            async with recovery.lock:
                await recovery.import_snapshot(entry['raw'],entry['keys'],replace_starter_aliases=True)
            staged.pop(stage,None)
            return JSONResponse({'ok':True},headers=headers)
        except Exception:return error(RecoveryError())
