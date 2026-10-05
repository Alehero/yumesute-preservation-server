"""Opt-in local credential vault; portable exports use a separate passphrase key.

Encryption protects stored credentials, not the authenticity of player progress.
"""
import base64
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt


def private_write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temp = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(data)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp): os.unlink(temp)


def portable_export(record, password):
    if not isinstance(password, str) or not 12 <= len(password) <= 1024:
        raise ValueError('Use a passphrase of 12–1024 characters.')
    salt = os.urandom(16)
    key = Scrypt(salt=salt, length=32, n=32768, r=8, p=1).derive(password.encode())
    return json.dumps({'format': 'yumesute-official-credential-v1',
        'kdf': 'scrypt-N32768-r8-p1', 'salt': base64.b64encode(salt).decode(),
        'ciphertext': Fernet(base64.urlsafe_b64encode(key)).encrypt(json.dumps(record).encode()).decode()}).encode()


def open_portable(data, password):
    obj = json.loads(data)
    if obj['format'] != 'yumesute-official-credential-v1' or obj['kdf'] != 'scrypt-N32768-r8-p1':
        raise ValueError('Unsupported credential format')
    salt = base64.b64decode(obj['salt'], validate=True)
    if len(salt) != 16: raise ValueError('Invalid salt')
    key = Scrypt(salt=salt, length=32, n=32768, r=8, p=1).derive(password.encode())
    return json.loads(Fernet(base64.urlsafe_b64encode(key)).decrypt(obj['ciphertext'].encode()))


class TokenVault:
    def __init__(self, root):
        self.root = Path(root) / 'private/official-credentials'

    @property
    def enabled(self):
        return (self.root / 'enabled').is_file()

    def enable(self, enabled):
        if enabled: private_write(self.root / 'enabled', b'1')
        else: (self.root / 'enabled').unlink(missing_ok=True)

    def cipher(self):
        path = self.root / 'key'
        if not path.exists():
            if self.root.exists() and any(self.root.glob('*.enc')):
                raise ValueError('Vault key missing; restore it from backup.')
            # Exclusive creation: never replace an existing encryption key.
            self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
            try:
                fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            except FileExistsError: pass
            else:
                with os.fdopen(fd, 'wb') as f: f.write(Fernet.generate_key())
        return Fernet(path.read_bytes())

    def save(self, uid, token, source):
        if not self.enabled: return
        record = {'user_id': int(uid), 'official_login_token': token,
                  'source': source, 'saved_at': datetime.now(timezone.utc).isoformat()}
        private_write(self.root / f'{int(uid)}.enc', self.cipher().encrypt(json.dumps(record).encode()))

    def has(self, uid):
        return (self.root / f'{int(uid)}.enc').is_file()

    def read(self, uid):
        return json.loads(self.cipher().decrypt((self.root / f'{int(uid)}.enc').read_bytes()))
