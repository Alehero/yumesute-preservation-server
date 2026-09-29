import sys
from pathlib import Path
from types import SimpleNamespace
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tunnel import LocalServer

class RoutingTest(unittest.TestCase):
    def flow(self,host,sni=None):
        return SimpleNamespace(request=SimpleNamespace(pretty_host=host,host=host,port=443,scheme='https',headers={}),server_conn=SimpleNamespace(sni=sni))
    def test_game_hostname(self):
        f=self.flow('assets-e.wds-stellarium.com');LocalServer(8125).request(f)
        self.assertEqual((f.request.host,f.request.port,f.request.scheme),('127.0.0.1',8125,'http'))
        self.assertEqual(f.request.headers['Host'],'assets-e.wds-stellarium.com')
    def test_transparent_ip_with_tls_name(self):
        f=self.flow('192.0.2.10','lb-api.wds-stellarium.com');LocalServer(8125).request(f)
        self.assertEqual(f.request.host,'127.0.0.1')
    def test_other_hosts_unchanged(self):
        f=self.flow('example.org');LocalServer(8125).request(f)
        self.assertEqual((f.request.host,f.request.port,f.request.scheme),('example.org',443,'https'))
