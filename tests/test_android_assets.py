"""Platform-separated download plans and account-preserving media repair."""
import hashlib,json,tempfile,unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch
import brotli
import download_data as d
import lifecycle as l

class AndroidAssets(unittest.TestCase):
    def catalog(self,platform):
        return {'m_InternalIdPrefixes':[f'http://2d-assets/{platform}/group/'],
                'm_InternalIds':['0#shared.bundle']}

    def test_platform_prefixes(self):
        self.assertEqual(d.bundle_paths(self.catalog('Android'),'2d-assets','Android'),['group/shared.bundle'])
        with self.assertRaises(ValueError):d.bundle_paths(self.catalog('iOS'),'2d-assets','Android')
        self.assertNotEqual(d.catalog_path('2d-assets','Android'),d.catalog_path('2d-assets','iOS'))

    def test_both_plan_is_platform_separated(self):
        with tempfile.TemporaryDirectory() as folder,ExitStack() as stack:
            root=Path(folder)
            def fetch(url,dest,expected):
                dest.parent.mkdir(parents=True,exist_ok=True)
                dest.write_bytes(b'master' if 'mastermemory' in url else brotli.compress(json.dumps(self.catalog('Android' if '/Android/' in url else 'iOS')).encode()))
                return {'status':'downloaded'}
            stack.enter_context(patch('server.bootstrap'))
            stack.enter_context(patch.object(d,'fetch',side_effect=fetch))
            stack.enter_context(patch.object(d,'catalog_hashes',return_value={'2d-assets':'unused'}))
            stack.enter_context(patch.object(d,'metadata_jobs',return_value=[('assets/Notations/1/1.enc','https://example.test/shared')]))
            stack.enter_context(patch.object(d,'story_supplement',return_value={}))
            stack.enter_context(patch('supplemental_resources.resources',return_value={}))
            d.run(root,metadata_only=True,platform='both')
            plan=dict(json.loads((root/'download-plan.json').read_text()))
            self.assertIn('/Android/',plan['assets/2d-assets/android/group/shared.bundle'])
            self.assertIn('/iOS/',plan['assets/2d-assets/ios/group/shared.bundle'])
            self.assertEqual(len(plan),3)
            self.assertTrue((root/'assets/2d-assets/android/catalog.json').exists())
            self.assertTrue((root/'assets/2d-assets/ios/catalog.json').exists())

    def test_android_repair_preserves_ios_accounts_and_checks_before_write(self):
        with tempfile.TemporaryDirectory() as folder,ExitStack() as stack:
            root=Path(folder)/'install';source=Path(folder)/'download'
            account=root/'private/account.json';account.parent.mkdir(parents=True);account.write_text('keep-account')
            ios=root/'vendor/server-of-dreams/_data/assets/2d-assets/ios/catalog.json';ios.parent.mkdir(parents=True);ios.write_text('keep-ios')
            packed=brotli.compress(json.dumps(self.catalog('Android')).encode())
            cat=source/d.catalog_path('2d-assets','Android');cat.parent.mkdir(parents=True);cat.write_bytes(packed)
            rel='assets/2d-assets/android/group/shared.bundle';bundle=source/rel;bundle.parent.mkdir(parents=True);bundle.write_bytes(b'android')
            (source/'download-report.jsonl').write_text(json.dumps({'path':rel,'status':'downloaded','sha256':hashlib.sha256(b'android').hexdigest()})+'\n')
            stack.enter_context(patch.object(d,'catalog_hashes',return_value={'2d-assets':hashlib.sha256(packed).hexdigest()}))
            stack.enter_context(patch.object(d,'story_supplement',return_value={}))
            stack.enter_context(patch('supplemental_resources.resources',return_value={}))
            cat.write_bytes(b'corrupt')
            with self.assertRaises(ValueError):l.install_verified_media(root,source,'android')
            self.assertFalse((root/'vendor/server-of-dreams/_data'/rel).exists())
            cat.write_bytes(packed)
            self.assertEqual(l.install_verified_media(root,source,'android'),1)
            self.assertEqual(l.install_verified_media(root,source,'android'),0)
            self.assertEqual(account.read_text(),'keep-account');self.assertEqual(ios.read_text(),'keep-ios')
            self.assertEqual((root/'vendor/server-of-dreams/_data'/rel).read_bytes(),b'android')

    def test_download_forwards_platform_and_blocks_incomplete(self):
        with patch.object(d,'run',return_value=2) as run:
            with self.assertRaises(RuntimeError):l.download(Path('data'),False,'android')
            run.assert_called_once_with(Path('data'),platform='android')
            self.assertEqual(l.download(Path('data'),True,'android'),2)
