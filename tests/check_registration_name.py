"""Run only in the disposable reroll-check installation/database."""
import asyncio
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'tools'), str(ROOT/'vendor/server-of-dreams')]
from helpers.config import database
database.database = 'yumesute_reroll_checks'
from serve import app, ACCOUNT
from helpers.auth import register, decode_jwt
from models import RegisterPayload
from starter_login import register_starter

async def main():
    assert app.config.database == 'yumesute_reroll_checks'
    async with app.router.lifespan_context(app):
        created = await register(RegisterPayload(name='Player'), app)
        uid = decode_jwt(created.token)
        state = dict(mode='fresh', user_id=uid, accept_registration_name=True)
        first = await register_starter(app, state, '星のひと')
        assert first.token
        await register_starter(app, state, 'Retry must not rename')
        async with app.acquire_db() as c:
            assert await c.conn.fetchval('SELECT name FROM user_profile WHERE "userId"=$1',uid) == '星のひと'
            assert await c.conn.fetchval('SELECT "tutorialStatus" FROM "user" WHERE "userId"=$1',uid) == 0
        assert not (await register_starter(app, dict(state,mode='import'), 'Other')).token
    print('PASS: Japanese registration name persisted once; retry preserves name; tutorial starts at zero; import rejected')
asyncio.run(main())
