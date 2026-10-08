import json
import stat
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from token_vault import TokenVault, portable_export, open_portable
from cryptography.fernet import InvalidToken

class VaultTests(unittest.TestCase):
    def test_default_on_restart_disable_and_permissions(self):
        with tempfile.TemporaryDirectory() as root:
            vault=TokenVault(root)
            vault.save(7,'test-official-secret','test')
            self.assertTrue(vault.has(7))
            restored=TokenVault(root)
            self.assertEqual(restored.read(7)['official_login_token'],'test-official-secret')
            for name in ['key','7.enc']:
                self.assertNotIn(b'test-official-secret',(vault.root/name).read_bytes())
                self.assertEqual(stat.S_IMODE((vault.root/name).stat().st_mode),0o600)
            vault.enable(False)
            self.assertFalse(TokenVault(root).enabled)
            vault.save(7,'replacement','test')
            self.assertEqual(restored.read(7)['official_login_token'],'test-official-secret')
            vault.enable(True)
            self.assertTrue(TokenVault(root).enabled)
            vault.save(7,'replacement','test')
            self.assertEqual(restored.read(7)['official_login_token'],'replacement')

    def test_portable_password_and_tampering(self):
        record={'user_id':7,'official_login_token':'test-secret'}
        data=portable_export(record,'long backup passphrase')
        self.assertNotIn(b'test-secret',data)
        self.assertEqual(open_portable(data,'long backup passphrase'),record)
        with self.assertRaises(InvalidToken):open_portable(data,'wrong passphrase')
        obj=json.loads(data);obj['ciphertext']=obj['ciphertext'][:-8]+'abcdefgh'
        with self.assertRaises(InvalidToken):open_portable(json.dumps(obj),'long backup passphrase')
        with self.assertRaises(ValueError):portable_export(record,'short')
