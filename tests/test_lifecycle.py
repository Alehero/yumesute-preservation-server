import argparse
from contextlib import ExitStack
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
import zipfile
import lifecycle as l


class Lifecycle(unittest.TestCase):
    def test_lock_blocks_parallel_and_releases_after_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            with self.assertRaises(ValueError):
                with l.installation_lock(root):
                    with self.assertRaises(RuntimeError):
                        with l.installation_lock(root): pass
                    raise ValueError('interrupted')
            with l.installation_lock(root): pass

    def test_existing_setup_never_downloads_or_prepares(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'private').mkdir();(root/'private/account.json').write_text('keep')
            server=Mock();args=argparse.Namespace()
            with patch.object(l,'require_stopped'),patch.object(l,'download') as download:
                l.setup(root,args,server)
            download.assert_not_called();server.prepare.assert_not_called();server.start.assert_called_once_with(args)
            self.assertEqual((root/'private/account.json').read_text(),'keep')

    def test_missing_downloads_stop_by_default(self):
        with patch('download_data.run',return_value=2):
            with self.assertRaises(RuntimeError):l.download(Path('data'),False)
            self.assertEqual(l.download(Path('data'),True),2)

    def test_existing_database_does_not_require_docker(self):
        with patch.object(l,'configuration',return_value={'database':{}}),patch.object(l,'database_ready',return_value=True),patch.object(l.subprocess,'run') as run:
            l.ensure_database(Path('.'));run.assert_not_called()

    def test_unavailable_external_database_not_started_or_reset(self):
        with patch.object(l,'configuration',return_value={'database':{}}),patch.object(l,'database_ready',return_value=False),patch.object(l,'managed_database',return_value=False),patch.object(l.subprocess,'run') as run:
            with self.assertRaises(RuntimeError):l.ensure_database(Path('.'))
            run.assert_not_called()

    def test_compose_database_start_waits_and_rechecks(self):
        with patch.object(l,'configuration',return_value={'database':{}}),patch.object(l,'database_ready',side_effect=[False,True]) as ready,patch.object(l,'managed_database',return_value=True),patch.object(l.shutil,'which',return_value='/docker'),patch.object(l.subprocess,'run',return_value=Mock(returncode=0)) as run:
            l.ensure_database(Path('.'))
            self.assertIn('--wait',run.call_args.args[0]);self.assertEqual(ready.call_count,2)

    def test_repair_validates_before_write_then_repairs_and_skips(self):
        with tempfile.TemporaryDirectory() as folder,ExitStack() as stack:
            root=Path(folder)/'install';source=Path(folder)/'source';source.mkdir();(root/'private/upstream').mkdir(parents=True)
            account=root/'private/account.json';account.write_text('keep save');helpfile=root/'private/upstream/help.bin';helpfile.write_bytes(b'old')
            good=hashlib.sha256(b'new').hexdigest()
            (source/'help.bin').write_bytes(b'bad')
            (source/'download-report.jsonl').write_text(json.dumps({'path':'help.bin','status':'downloaded','sha256':good})+'\n')
            stack.enter_context(patch('supplemental_resources.resources',return_value={'help.bin':{'sha256':good}}))
            stack.enter_context(patch('download_data.story_supplement',return_value={}))
            stack.enter_context(patch('download_data.CATALOG_HASHES',{}))
            with self.assertRaises(ValueError):l.install_verified_media(root,source)
            self.assertEqual(helpfile.read_bytes(),b'old')
            (source/'help.bin').write_bytes(b'new');self.assertEqual(l.install_verified_media(root,source),1)
            self.assertEqual(l.install_verified_media(root,source),0)
            self.assertEqual(account.read_text(),'keep save');self.assertEqual(helpfile.read_bytes(),b'new')

    def test_repair_rejects_account_and_traversal_paths(self):
        for path in ['private/account.json','assets/../../private/account.json','master-original.db','/tmp/a']:
            with self.assertRaises(ValueError):l.media_destination(Path('.'),path)

    def test_atomic_copy_failure_preserves_installed_file(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);src=root/'source';dest=root/'dest';src.write_bytes(b'bad');dest.write_bytes(b'old')
            with self.assertRaises(ValueError):l.atomic_copy(src,dest,hashlib.sha256(b'good').hexdigest())
            self.assertEqual(dest.read_bytes(),b'old');self.assertFalse((root/'dest.repairing').exists())

    def test_backup_includes_private_media_external_ca_and_verified_manifest(self):
        with tempfile.TemporaryDirectory() as folder,ExitStack() as stack:
            root=Path(folder)/'install';(root/'private').mkdir(parents=True)
            (root/'vendor/server-of-dreams/.git').mkdir(parents=True)
            (root/'vendor/server-of-dreams/.git/HEAD').write_text('pinned revision')
            (root/'private/account.json').write_text('saved');(root/'private/photo.png').write_bytes(b'photo')
            (root/'data').mkdir();(root/'data/duplicate').write_text('exclude')
            ca=Path(folder)/'ca';ca.mkdir();(ca/'mitmproxy-ca.pem').write_text('private test key')
            (root/'private/certificate-store.json').write_text(json.dumps({'ca_dir':str(ca)}))
            out=Path(folder)/'backup.zip'
            stack.enter_context(patch.object(l,'require_stopped'))
            stack.enter_context(patch.object(l,'configuration',return_value={'database':{'host':'localhost','port':5432,'username':'test','password':'secret','database':'test'}}))
            stack.enter_context(patch.object(l,'database_ready',return_value=True))
            stack.enter_context(patch.object(l.shutil,'which',return_value='/pg_dump'))
            def dump(*args,**kwargs):kwargs['stdout'].write(b'PGDMPfixture');return Mock(returncode=0)
            run=stack.enter_context(patch.object(l.subprocess,'run',side_effect=dump))
            l.backup(root,argparse.Namespace(output=str(out)))
            self.assertNotIn('secret',str(run.call_args.args))
            with zipfile.ZipFile(out) as z:
                manifest=json.loads(z.read('backup-manifest.json'))['sha256']
                self.assertIn('installation/vendor/server-of-dreams/.git/HEAD',manifest)
                self.assertIn('installation/private/account.json',manifest)
                self.assertIn('installation/private/photo.png',manifest)
                self.assertIn('installation/private/backup-ca/mitmproxy-ca.pem',manifest)
                self.assertNotIn('installation/data/duplicate',manifest)
                for name,expected in manifest.items():self.assertEqual(hashlib.sha256(z.read(name)).hexdigest(),expected)
            with self.assertRaises(RuntimeError):l.backup(root,argparse.Namespace(output=str(out)))

    def test_failed_dump_does_not_publish_backup(self):
        with tempfile.TemporaryDirectory() as folder,ExitStack() as stack:
            root=Path(folder);out=root/'backup.zip'
            stack.enter_context(patch.object(l,'require_stopped'))
            stack.enter_context(patch.object(l,'configuration',return_value={'database':{'host':'localhost','port':5432,'username':'test','password':'secret','database':'test'}}))
            stack.enter_context(patch.object(l,'database_ready',return_value=True))
            stack.enter_context(patch.object(l.shutil,'which',return_value='/pg_dump'))
            stack.enter_context(patch.object(l.subprocess,'run',side_effect=RuntimeError('dump failed')))
            with self.assertRaises(RuntimeError):l.backup(root,argparse.Namespace(output=str(out)))
            self.assertFalse(out.exists());self.assertFalse(list(root.glob('.yumesute-backup-*')))

if __name__=='__main__':unittest.main()
