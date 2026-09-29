import gzip
import base64
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
    @property
    def raw(self): return self
    def stream(self, size, decode_content=False): yield b'abc'

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

    def test_gzip_verifies_wire_size_and_decoded_checksum(self):
        packed = gzip.compress(b'abc')
        response = Response()
        response.headers = {'Content-Length': str(len(packed)), 'Content-Encoding': 'gzip',
                            'Content-MD5': base64.b64encode(hashlib.md5(packed).digest()).decode()}
        response.stream = lambda *args, **kwargs: iter([packed])
        with tempfile.TemporaryDirectory() as folder, patch.object(d.requests, 'get', return_value=response):
            dest = Path(folder) / 'scene.bin'
            result = d.fetch(d.BASE + '/scene.bin', dest, hashlib.sha256(b'abc').hexdigest())
            self.assertEqual(result['status'], 'downloaded')
            self.assertEqual(dest.read_bytes(), b'abc')

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

class StoryDownloads(unittest.TestCase):
    def test_supplement_has_exact_known_gaps(self):
        entries = d.story_supplement()
        self.assertEqual(len(entries), 30)
        self.assertEqual(sum(x['metadata']['story_type'] == 1 for x in entries.values()), 20)
        self.assertEqual(sum(x['metadata']['story_type'] == 3 for x in entries.values()), 10)
        self.assertIn('1050101', entries)
        self.assertIn('150052', entries)

    def test_manifest_requires_verified_scene_and_preserves_other_entries(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            entry = {'metadata': {'episode_detail_asset_source': 'scenes/1_ab.bin'},
                     'sha256': hashlib.sha256(b'abc').hexdigest()}
            (root/'episode-manifest.json').write_text(json.dumps({'existing': {'title': 'kept'}}))
            d.save_story_manifest(root, {'1': entry})
            self.assertNotIn('1', json.loads((root/'episode-manifest.json').read_text()))
            (root/'scenes').mkdir(); (root/'scenes/1_ab.bin').write_bytes(b'bad')
            d.save_story_manifest(root, {'1': entry})
            self.assertNotIn('1', json.loads((root/'episode-manifest.json').read_text()))
            (root/'scenes/1_ab.bin').write_bytes(b'abc')
            d.save_story_manifest(root, {'1': entry})
            result = json.loads((root/'episode-manifest.json').read_text())
            self.assertEqual(result['1'], entry['metadata'])
            self.assertEqual(result['existing'], {'title': 'kept'})

if __name__ == '__main__': unittest.main()
