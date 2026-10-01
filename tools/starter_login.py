"""Single-save onboarding; imported saves always require explicit authentication."""
from db.account import get_account_by_id, update_account_token
from helpers.auth import make_jwt, make_session_jwt
from models import AccountRegistResult, AuthenticateResult


async def starter_token(app, account, *, session=False, name=None):
    if account.get('mode') != 'fresh':
        return None
    uid = account['user_id']
    async with app.acquire_db() as conn, conn.transaction():
        row = await conn.fetchrow(get_account_by_id(uid))
        if row is None or row.banLevel:
            return None
        if account.get('accept_registration_name') and isinstance(name, str) and name.strip():
            # A transaction makes the first name durable and retries non-destructive.
            await conn.conn.execute('CREATE TABLE IF NOT EXISTS preservation_registration (user_id bigint PRIMARY KEY)')
            claimed = await conn.conn.fetchval('INSERT INTO preservation_registration(user_id) VALUES ($1) ON CONFLICT DO NOTHING RETURNING user_id', uid)
            if claimed is not None:
                await conn.conn.execute('UPDATE user_profile SET name=$2 WHERE "userId"=$1', uid, name)
        token = make_session_jwt(uid, 'AppStore') if session else make_jwt(uid)
        await conn.execute(update_account_token(uid, token))
    return token


async def register_starter(app, account, name=None):
    token = await starter_token(app, account, name=name)
    return AccountRegistResult(token=token or '', error_type=0 if token else 1)


async def authenticate_starter(payload, app, account):
    # A foreign/stale nonempty token must not silently select a different save.
    if payload is None or payload.login_token:
        return None
    token = await starter_token(app, account, session=True)
    return AuthenticateResult(token=token, ban_level=0) if token else None
