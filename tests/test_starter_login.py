import importlib.util
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

ROOT = Path(__file__).resolve().parents[1]

class StarterLoginTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.conn = Mock()
        self.conn.fetchrow = AsyncMock(return_value=types.SimpleNamespace(banLevel=0))
        self.conn.execute = AsyncMock()
        context = AsyncMock()
        context.__aenter__.return_value = self.conn
        self.conn.transaction.return_value = AsyncMock()
        self.conn.conn = Mock(execute=AsyncMock(), fetchval=AsyncMock(return_value=7))
        self.app = Mock()
        self.app.acquire_db.return_value = context
        self.state = {'mode': 'fresh', 'user_id': 7}
        modules = {
            'db.account': types.SimpleNamespace(get_account_by_id=lambda uid: uid, update_account_token=lambda uid,t: (uid,t)),
            'helpers.auth': types.SimpleNamespace(make_jwt=lambda uid:f'register:{uid}', make_session_jwt=lambda uid,p:f'session:{uid}'),
            'models': types.SimpleNamespace(AccountRegistResult=types.SimpleNamespace, AuthenticateResult=types.SimpleNamespace),
        }
        with patch.dict(sys.modules, modules):
            spec = importlib.util.spec_from_file_location('test_starter_module', ROOT/'tools/starter_login.py')
            self.module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(self.module)

    async def test_registration_reuses_save_and_only_updates_token(self):
        for _ in range(2):
            result = await self.module.register_starter(self.app, self.state)
            self.assertEqual((result.token, result.error_type), ('register:7', 0))
        self.assertEqual(self.conn.execute.await_count, 2)
        self.conn.execute.assert_awaited_with((7, 'register:7'))

    async def test_name_claimed_once_only_for_new_accounts(self):
        state = dict(self.state, accept_registration_name=True)
        self.conn.conn.fetchval.side_effect = [7, None]
        await self.module.register_starter(self.app, state, 'ことな')
        await self.module.register_starter(self.app, state, 'Retry')
        updates = [c for c in self.conn.conn.execute.call_args_list if c.args[0].startswith('UPDATE')]
        self.assertEqual(len(updates), 1)
        self.assertEqual(updates[0].args[1:], (7, 'ことな'))
        self.conn.conn.execute.reset_mock()
        await self.module.register_starter(self.app, self.state, 'Existing save')
        self.conn.conn.execute.assert_not_awaited()

    async def test_import_never_auto_selected(self):
        state = dict(self.state, mode='import')
        self.assertEqual((await self.module.register_starter(self.app, state)).error_type, 1)
        self.assertIsNone(await self.module.authenticate_starter(types.SimpleNamespace(login_token=''), self.app, state))
        self.app.acquire_db.assert_not_called()

    async def test_blank_auth_works_foreign_token_does_not_fallback(self):
        result = await self.module.authenticate_starter(types.SimpleNamespace(login_token=''), self.app, self.state)
        self.assertEqual(result.token, 'session:7')
        self.app.acquire_db.reset_mock()
        for payload in [None, types.SimpleNamespace(login_token='foreign-token')]:
            self.assertIsNone(await self.module.authenticate_starter(payload, self.app, self.state))
        self.app.acquire_db.assert_not_called()

    async def test_missing_or_banned_save_rejected(self):
        for row in [None, types.SimpleNamespace(banLevel=1)]:
            self.conn.fetchrow.return_value = row
            self.assertEqual((await self.module.register_starter(self.app, self.state)).error_type, 1)
        self.conn.execute.assert_not_awaited()

class StartupTests(unittest.TestCase):
    def test_only_missing_account_triggers_creation(self):
        import server
        with tempfile.TemporaryDirectory() as tmp, patch.object(server, 'PRIVATE', Path(tmp)), patch.object(server, 'account', new_callable=AsyncMock) as create:
            server.ensure_start_account()
            self.assertEqual(create.call_args.args[0].command, 'fresh-account')
            self.assertEqual(create.call_args.args[0].name, 'Player')
            (Path(tmp)/'account.json').write_text('{"mode":"import"}')
            server.ensure_start_account()
            self.assertEqual(create.await_count, 1)
