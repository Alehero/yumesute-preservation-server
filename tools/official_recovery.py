"""Bounded official-account recovery. Local identities always win; imports are insert-only."""
import asyncio
import hashlib
import hmac
import json
import secrets
import time
from pathlib import Path

import httpx
from helpers.config import config
from helpers.auth import decode_jwt, make_session_jwt
from helpers.msgpack import pack
from helpers.user_data import _table
from db.account import create_account, add_hash_user_id, get_account_by_id, update_account_token
from db import user as queries
from models import AuthenticatePayload
from models.unions import IDATA_OBJECT
from protocol import envelope, inspect_snapshot, unpack_stream, expand
from import_account import row_dict
from account_compat import merge_account

ORIGIN = 'https://lb-api.wds-stellarium.com'
MAX_BYTES = 64 * 1024 * 1024

class RecoveryError(Exception):
    """Messages must never include credentials or response bodies."""
    def __init__(self, code='RecoveryFailed', faults=None):
        super().__init__(code)
        self.code, self.faults = code, faults

class Unavailable(RecoveryError):
    pass

class Rejected(RecoveryError):
    pass


def credential_key(kind, value):
    # Keyed digests avoid storing passwords, tokens or fast password-verification hashes.
    data=json.dumps([kind,value],ensure_ascii=False,separators=(',',':')).encode()
    return hmac.new(str(config['jwt_secret']).encode(),data,hashlib.sha256).hexdigest()


class OfficialClient:
    def __init__(self, transport=None):
        self.transport = transport

    async def request(self, path, payload=None, token=None):
        headers={'Accept':'application/vnd.msgpack','Content-Type':'application/vnd.msgpack','X-Platform':'app-store','X-FM':'0','User-Agent':'BestHTTP/2 v2.8.5'}
        if token: headers['Authorization']='Bearer '+token
        try:
            async with httpx.AsyncClient(timeout=12,follow_redirects=False,trust_env=False,transport=self.transport) as client:
                async with client.stream('GET' if payload is None else 'POST', ORIGIN+path,
                                         headers=headers,content=None if payload is None else pack(payload)) as r:
                    if r.status_code >= 500: raise Unavailable('OfficialUnavailable')
                    if r.status_code != 200: raise RecoveryError('OfficialRequestRejected')
                    data=bytearray()
                    async for part in r.aiter_bytes():
                        data.extend(part)
                        if len(data)>MAX_BYTES: raise RecoveryError('OfficialResponseTooLarge')
        except (httpx.TimeoutException,httpx.NetworkError):
            raise Unavailable('OfficialUnavailable') from None
        try:
            parts=[expand(x) for x in unpack_stream(bytes(data))]
            if len(parts)!=5 or not isinstance(parts[0],list): raise ValueError()
        except Exception:
            raise RecoveryError('InvalidOfficialResponse') from None
        if parts[0]:
            # Only explicit service-closure codes permit fallback. Unknown faults fail closed.
            codes={x[0] for x in parts[0] if isinstance(x,list) and x and isinstance(x[0],str)}
            if codes and codes <= {'ServiceEnded','EndOfService','ServiceUnavailable'}:
                raise Unavailable('OfficialServiceEnded')
            raise Rejected('OfficialAccountRejected',parts[0])
        return parts[1],bytes(data)

    async def recover(self, *, auth=None, transfer=None):
        rules=json.loads((Path(__file__).resolve().parents[1]/'preservation-rules.json').read_text())
        if rules.get('official_account_recovery', True) is False:
            raise Unavailable('OfficialRecoveryDisabled')
        async with asyncio.timeout(40):
            expected=None
            if transfer is not None:
                result,_=await self.request('/api/Account/GetTakeOverAccount',transfer)
                if not isinstance(result,list) or len(result)<5: raise RecoveryError('InvalidTransferResponse')
                if result[0] is not True: raise Rejected('OfficialAccountNotFound')
                expected=result[1]
                auth=AuthenticatePayload(login_token=result[4],game_version=1,application_version='2.31.3.425')
            result,_=await self.request('/api/Account/Authenticate',auth)
            if not isinstance(result,list) or len(result)<2: raise RecoveryError('InvalidAuthenticationResponse')
            if result[1] or not isinstance(result[0],str) or not result[0]: raise Rejected('OfficialAccountRejected')
            _,raw=await self.request('/api/data/user',token=result[0])
            try:
                inspect_snapshot(raw)
            except (ValueError, TypeError, IndexError, KeyError):
                raise RecoveryError("InvalidRecoveredSnapshot") from None
            if expected is not None:
                rows=envelope(raw)[1]
                user=next(v for v in rows if v and v[0]==0)[1]
                # The transfer response exposes the hash user ID; do not infer numeric identity.
                if len(user)<=13 or str(user[13])!=str(expected): raise RecoveryError('OfficialIdentityMismatch')
            return raw, auth.login_token


class Recovery:
    def __init__(self,app,account,official=None):
        self.app,self.account,self.official=app,account,official or OfficialClient()
        self.ready=False
        self.lock=asyncio.Lock()

    async def setup(self):
        if self.ready:return
        async with self.lock:
            if self.ready:return
            async with self.app.acquire_db() as c,c.transaction():
                await c.conn.execute('CREATE TABLE IF NOT EXISTS preservation_recovery (user_id bigint PRIMARY KEY REFERENCES accounts("userId"), snapshot bytea NOT NULL, baseline bytea NOT NULL)')
                await c.conn.execute('CREATE TABLE IF NOT EXISTS preservation_credentials (digest text PRIMARY KEY, user_id bigint NOT NULL REFERENCES accounts("userId"), source text NOT NULL)')
            self.ready=True

    async def lookup(self,key):
        await self.setup()
        async with self.app.acquire_db() as c:
            return await c.conn.fetchval('SELECT user_id FROM preservation_credentials WHERE digest=$1',key)

    async def local_token_uid(self,token):
        uid=decode_jwt(token,verify_exp=False)
        if uid is not None:
            async with self.app.acquire_db() as c:
                if await c.fetchrow(get_account_by_id(uid)):return uid
            # A locally signed token with no save is corruption, not a recovery opportunity.
            raise RecoveryError('LocalAccountMissing')
        return await self.lookup(credential_key('token',token))

    async def session(self,uid):
        async with self.app.acquire_db() as c:
            row=await c.fetchrow(get_account_by_id(uid))
            if row is None:raise RecoveryError('LocalAccountMissing')
            if row.banLevel:raise Rejected('LocalAccountUnavailable')
            token=make_session_jwt(uid,'AppStore')
            await c.execute(update_account_token(uid,token))
            return token

    async def resolve(self,*,auth=None,transfer=None):
        value=auth.login_token if auth is not None else [transfer.linkage_code,transfer.password]
        key=credential_key('token' if auth is not None else 'transfer',value)
        uid=await self.local_token_uid(value) if auth is not None else await self.lookup(key)
        if uid is not None:return uid
        # Only one previously unseen recovery at a time; retries recheck the committed mapping.
        async with self.lock:
            uid=await self.lookup(key)
            if uid is not None:return uid
            try:
                raw,login_token=await self.official.recover(auth=auth,transfer=transfer)
            except (Unavailable,TimeoutError):
                return await self.fallback(key)
            return await self.import_snapshot(raw,[key,credential_key('token',login_token)])

    async def fallback(self,key):
        # Never replace any save. Only associate an unrecognized credential with the
        # installation's existing starter, and never after an official recovery.
        if self.account.get('mode')!='fresh':raise Unavailable('OfficialUnavailableLocalSavePreserved')
        uid=self.account['user_id']
        async with self.app.acquire_db() as c,c.transaction():
            await c.conn.execute('LOCK TABLE accounts IN EXCLUSIVE MODE')
            existing=await c.conn.fetchval('SELECT user_id FROM preservation_credentials WHERE digest=$1',key)
            if existing is not None:return existing
            if await c.conn.fetchval('SELECT EXISTS(SELECT 1 FROM preservation_recovery)'):
                raise Unavailable('OfficialUnavailableLocalSavePreserved')
            if not await c.fetchrow(get_account_by_id(uid)):raise RecoveryError('LocalAccountMissing')
            await c.conn.execute("INSERT INTO preservation_credentials VALUES($1,$2,'starter-fallback')",key,uid)
        return uid

    async def import_snapshot(self,raw,keys):
        try:
            summary=inspect_snapshot(raw)
        except (ValueError, TypeError, IndexError, KeyError):
            raise RecoveryError('InvalidRecoveredSnapshot') from None
        uid=summary['user_id'];rows=[]
        for item in envelope(raw)[1]:
            if item is None:continue
            name=IDATA_OBJECT.get(item[0]);fn=getattr(queries,'upsert_'+_table(name),None) if name else None
            if fn is None:raise RecoveryError('UnsupportedRecoveredEntity')
            try:
                rows.append((name,fn,row_dict(name,item[1])))
            except (ValueError, TypeError, IndexError, KeyError):
                raise RecoveryError('InvalidRecoveredEntity') from None
        if not any(n=='UserProfile' for n,_,_ in rows):raise RecoveryError('IncompleteRecoveredAccount')
        async with self.app.acquire_db() as c,c.transaction():
            await c.conn.execute('LOCK TABLE accounts IN EXCLUSIVE MODE')
            prior=[await c.conn.fetchval('SELECT user_id FROM preservation_credentials WHERE digest=$1',k) for k in keys]
            if any(x is not None and x!=uid for x in prior):raise RecoveryError('CredentialAlreadyLinked')
            exists=await c.fetchrow(get_account_by_id(uid))
            if not exists:
                # This preview permits one recovered identity, preserving the original starter.
                if await c.conn.fetchval('SELECT EXISTS(SELECT 1 FROM preservation_recovery)') or self.account.get('mode')=='import':
                    raise RecoveryError('InstallationAlreadyHasSavedAccount')
                await c.execute(create_account(uid,secrets.token_urlsafe(32),'AppStore',int(time.time()),int(time.time())))
                for _,fn,row in rows:await c.execute(fn(uid,row))
                u=next(row for name,_,row in rows if name=='User')
                await c.execute(add_hash_user_id(u['hashUserId'],uid))
                # Read back through this transaction; no partial import or filesystem marker.
                from helpers.user_data import build_present,_ALL_TYPES
                class Bound:
                    def acquire_db(self):
                        from contextlib import asynccontextmanager
                        @asynccontextmanager
                        async def acquire():yield c
                        return acquire()
                baseline=await build_present(Bound(),uid,*_ALL_TYPES)
                await c.conn.execute('INSERT INTO preservation_recovery VALUES($1,$2,$3)',uid,raw,pack(baseline))
            elif not await c.conn.fetchval('SELECT EXISTS(SELECT 1 FROM preservation_recovery WHERE user_id=$1)',uid) and not (self.account.get('mode')=='import' and self.account.get('user_id')==uid):
                raise RecoveryError('LocalIdentityConflict')
            # Existing accounts are NEVER reimported: preserve all subsequent local progress.
            for key in keys:
                await c.conn.execute("INSERT INTO preservation_credentials VALUES($1,$2,'official') ON CONFLICT(digest) DO NOTHING",key,uid)
        return uid

    async def merge(self,uid,current):
        await self.setup()
        async with self.app.acquire_db() as c:
            row=await c.conn.fetchrow('SELECT snapshot,baseline FROM preservation_recovery WHERE user_id=$1',uid)
        if row:
            from helpers.msgpack import unpack
            return merge_account(envelope(row['snapshot'])[1],unpack(row['baseline']),current)
        return current
