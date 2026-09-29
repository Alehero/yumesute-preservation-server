import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import download_data as d

class Response:
    status_code = 200
    headers = {'Content-Length': '3', 'Content-Type': 'application/octet-stream'}
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def iter_content(self, size): yield b'abc'

class Downloads(unittest.TestCase):
    def test_catalog_paths_and_deduplication(self):
        c = {'m_InternalIdPrefixes': ['http://3d-assets/iOS/group/'],
             'm_InternalIds': ['0#172(10172).bundle', '0#172(10172).bundle', 'x.prefab']}
        self.assertEqual(d.bundle_paths(c, '3d-assets'), ['group/172(10172).bundle'])
        c['m_InternalIds'] = ['http://elsewhere/a.bundle']
        with self.assertRaises(ValueError): d.bundle_paths(c, '3d-assets')

    def test_reject_paths_and_other_hosts(self):
        for path in ('../x', '/x', 'x//y', 'x/../y', '%2e%2e/x', 'x\\y', 'x?y', 'x:y'):
            with self.assertRaises(ValueError): d.safe_path(path)
        with self.assertRaises(ValueError): d.fetch('https://elsewhere/x', Path('unused'))

    def test_resume_verifies_and_repairs_corruption(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(d.requests, 'get', return_value=Response()) as get:
            dest = Path(folder) / 'a.bundle'
            self.assertEqual(d.fetch(d.BASE + '/a.bundle', dest)['status'], 'downloaded')
            self.assertEqual(d.fetch(d.BASE + '/a.bundle', dest)['status'], 'verified-existing')
            self.assertEqual(get.call_count, 1)
            dest.write_bytes(b'bad')
            self.assertEqual(d.fetch(d.BASE + '/a.bundle', dest)['status'], 'downloaded')
            self.assertEqual(dest.read_bytes(), b'abc')
            self.assertFalse(dest.with_name('a.bundle.part').exists())

    def test_missing_or_redirect_does_not_save(self):
        for status in (404, 403, 302):
            response = Response(); response.status_code = status
            with tempfile.TemporaryDirectory() as folder, patch.object(d.requests, 'get', return_value=response):
                dest = Path(folder) / 'file'
                self.assertEqual(d.fetch(d.BASE + '/file', dest)['status'], f'HTTP {status}')
                self.assertFalse(dest.exists())

    def test_hash_or_length_failure_keeps_existing_file(self):
        for headers, expected in ((Response.headers, '0'*64), ({'Content-Length':'4'}, None)):
            response = Response(); response.headers = headers
            with tempfile.TemporaryDirectory() as folder, patch.object(d.requests, 'get', return_value=response), patch.object(d.time, 'sleep'):
                dest = Path(folder) / 'file'; dest.write_bytes(b'original')
                self.assertEqual(d.fetch(d.BASE + '/file', dest, expected)['status'], 'failed')
                self.assertEqual(dest.read_bytes(), b'original')
                self.assertFalse(dest.with_name('file.part').exists())

if __name__ == '__main__': unittest.main()
