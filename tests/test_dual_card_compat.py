import importlib.util
import sys
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

ROOT = Path(__file__).resolve().parents[1]


class DualCards(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        masters = {
            150050: SimpleNamespace(id_=150050, character_base_master_id=102, secondary_character_base_master_id=101),
            110010: SimpleNamespace(id_=110010, character_base_master_id=101, secondary_character_base_master_id=None),
        }
        self.bases = {101: 9001, 102: 9002}  # owned CharacterBase id per idol
        ids = iter(range(500, 600))
        modules = {n: types.ModuleType(n) for n in ('helpers', 'helpers.cache', 'helpers.things', 'db', 'db.user', 'db.user.grant')}
        modules['helpers.cache'].cache = SimpleNamespace(character_master=list(masters.values()))
        modules['helpers.things']._by_id = lambda table: masters if table == 'character_master' else {}
        modules['helpers.things']._random_id = lambda: next(ids)
        modules['db.user.grant'].get_character_base = lambda uid, base: ('base', base)
        modules['db.user.grant'].create_character_base = lambda *a: ('create', a)
        self.modules = modules
        with patch.dict(sys.modules, modules):
            spec = importlib.util.spec_from_file_location('test_dual_card_module', ROOT/'tools/dual_card_compat.py')
            self.dual = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(self.dual)
        self.conn = Mock()
        self.conn.fetchrow = AsyncMock(side_effect=lambda q: SimpleNamespace(id=self.bases[q[1]]) if q[1] in self.bases else None)
        self.conn.execute = AsyncMock()
        self.conn.conn = Mock(execute=AsyncMock(), fetch=AsyncMock(return_value=[]))

    async def call(self, fn, *args):
        with patch.dict(sys.modules, self.modules):
            return await fn(*args)

    async def test_grant_links_the_second_idol(self):
        await self.call(self.dual.grant_character, self.conn, 1, 150050)
        args = self.conn.conn.execute.await_args.args
        self.assertIn('"secondaryCharacterBaseId"', args[0])
        self.assertEqual(args[1:], (1, 500, 150050, 9002, 9001, 1))

    async def test_grant_single_idol_card_is_unchanged(self):
        await self.call(self.dual.grant_character, self.conn, 1, 110010)
        self.assertEqual(self.conn.conn.execute.await_args.args[1:], (1, 500, 110010, 9001, None, 0))

    async def test_second_idol_base_is_created_when_missing(self):
        del self.bases[101]
        await self.call(self.dual.grant_character, self.conn, 1, 150050)
        self.conn.execute.assert_awaited_once_with(('create', (1, 500, 101, None, 150050)))
        self.assertEqual(self.conn.conn.execute.await_args.args[5], 500)

    async def test_repair_fills_saved_dual_cards(self):
        self.conn.conn.fetch.return_value = [{'userId': 1, 'id': 4848299183, 'characterMasterId': 150050}]
        self.assertEqual(await self.call(self.dual.repair_dual_cards, self.conn), 1)
        self.assertEqual(self.conn.conn.fetch.await_args.args[1], [150050])
        self.assertEqual(self.conn.conn.execute.await_args.args[1:], (1, 4848299183, 9001))


if __name__ == '__main__':
    unittest.main()
