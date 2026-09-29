import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import server

class StarterResources(unittest.TestCase):
    def amount(self, value):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'preservation-rules.json').write_text(json.dumps(value))
            with patch.object(server,'ROOT',root):return server.fresh_song_tickets()
    def test_default_generous_allowance(self):self.assertEqual(self.amount({}),10000)
    def test_configurable_including_zero(self):
        self.assertEqual(self.amount({'fresh_song_tickets':0}),0)
        self.assertEqual(self.amount({'fresh_song_tickets':1234}),1234)
    def test_reject_invalid_allowance(self):
        for value in (-1,1000001,True,1.5,'10000'):
            with self.assertRaises(ValueError):self.amount({'fresh_song_tickets':value})

if __name__=='__main__':unittest.main()
