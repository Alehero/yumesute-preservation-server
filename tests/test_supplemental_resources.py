import hashlib,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import supplemental_resources as s
import download_data as d

class SupplementalResources(unittest.TestCase):
    def test_inventory_paths_counts_and_help(self):
        files=s.resources()
        self.assertEqual(len(files),1133)
        self.assertEqual(sum('/Textures/Help/' in x for x in files),30)
        self.assertEqual(files['help.bin']['url_path'],'/master-data/production/help.bin')
        self.assertEqual(sum(x['bytes'] for x in files.values()),49943880)

    def test_invalid_manifest_path_cannot_install_outside_root(self):
        good={'url_path':'/production/static-assets/Resources/Textures/../outside','sha256':'a'*64,'bytes':1}
        with patch.object(s.json,'loads',return_value={'format_version':1,'files':{'static-assets'+good['url_path']:good}}):
            with self.assertRaises(ValueError):s.resources()

    def test_install_validates_all_before_writes_and_preserves_accounts(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'data';source.mkdir();target=root/'install';(target/'private/upstream').mkdir(parents=True)
            (target/'private/account.json').write_text('keep account')
            (target/'private/upstream/help.bin').write_bytes(b'previous')
            entries={'help.bin':{'sha256':hashlib.sha256(b'help').hexdigest(),'bytes':4},'static-assets/production/static-assets/Resources/Textures/Test.png':{'sha256':hashlib.sha256(b'image').hexdigest(),'bytes':5}}
            (source/'help.bin').write_bytes(b'help')
            with patch.object(s,'resources',return_value=entries):
                with self.assertRaises(ValueError):s.install_resources(source,target)
                self.assertEqual((target/'private/upstream/help.bin').read_bytes(),b'previous')
                image=source/list(entries)[1];image.parent.mkdir(parents=True);image.write_bytes(b'wrong')
                with self.assertRaises(ValueError):s.install_resources(source,target)
                image.write_bytes(b'image')
                self.assertEqual(s.install_resources(source,target),2)
                self.assertEqual(s.install_resources(source,target),2)
            self.assertEqual((target/'private/upstream/help.bin').read_bytes(),b'help')
            self.assertEqual((target/'private'/list(entries)[1]).read_bytes(),b'image')
            self.assertEqual((target/'private/account.json').read_text(),'keep account')

    def test_supplemental_download_pins_hashes_and_reports_missing(self):
        with tempfile.TemporaryDirectory() as folder:
            files={'help.bin':{'url_path':'/master-data/production/help.bin','sha256':'a'*64,'bytes':4}}
            with patch.object(s,'resources',return_value=files),patch.object(d,'fetch',return_value={'status':'HTTP 404'}) as fetch:
                self.assertEqual(d.run(folder,supplemental_only=True),2)
                fetch.assert_called_once_with(d.BASE+'/master-data/production/help.bin',Path(folder).resolve()/'help.bin','a'*64)
            report=json.loads((Path(folder)/'download-report.jsonl').read_text())
            self.assertEqual(report['status'],'HTTP 404')
            self.assertFalse((Path(folder)/'help.bin').exists())

if __name__=='__main__':unittest.main()
