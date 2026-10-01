"""Single-save onboarding; imported saves always require explicit authentication."""
from db.account import get_account_by_id, update_account_token
from helpers.auth import make_jwt, make_session_jwt
from models import AccountRegistResult, AuthenticateResult


async def starter_token(app, account, *, session=False):
    if account.get('mode') != 'fresh':
        return None
    uid = account['user_id']
    async with app.acquire_db() as conn:
        row = await conn.fetchrow(get_account_by_id(uid))
        if row is None or row.banLevel:
            return None
        token = make_session_jwt(uid, 'AppStore') if session else make_jwt(uid)
        await conn.execute(update_account_token(uid, token))
    return token


async def register_starter(app, account):
    token = await starter_token(app, account)
    return AccountRegistResult(token=token or '', error_type=0 if token else 1)


async def authenticate_starter(payload, app, account):
    # A foreign/stale nonempty token must not silently select a different save.
    if payload is None or payload.login_token:
        return None
    token = await starter_token(app, account, session=True)
    return AuthenticateResult(token=token, ban_level=0) if token else None
