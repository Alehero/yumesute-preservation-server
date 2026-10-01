"""Check starter entry on the local fresh-account test server; no save reset."""
import json
import sys
from pathlib import Path
import httpx
import msgpack
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from protocol import envelope
state = json.loads((ROOT/'private/account.json').read_text())
assert state['mode'] == 'fresh', 'Only run against a fresh-mode local test installation'
base = 'http://127.0.0.1:8125'
def post(path, data):
    r = httpx.post(base+path, content=msgpack.packb(data), timeout=30)
    r.raise_for_status()
    assert r.headers.get('X-Yumesute-Backend') == 'local-preservation'
    return envelope(r.content)[1]
def data(token):
    r = httpx.get(base+'/api/data/user', headers={'Authorization':'Bearer '+token}, timeout=30)
    r.raise_for_status()
    return envelope(r.content)[1]
lines = (ROOT/'private/linking-credentials.txt').read_text().splitlines()
linked = post('/api/Account/GetTakeOverAccount', [state['transfer']['code'], lines[2].split(': ',1)[1]])
baseline = data(post('/api/Account/Authenticate', [linked[4],1,None,None,'2.31.3'])[0])
for _ in range(2):
    registered = post('/api/Account/Register', ['Player'])
    assert registered[0] and registered[1] == 0
    token = post('/api/Account/Authenticate', [registered[0],1,None,None,'2.31.3'])[0]
    assert token and data(token) == baseline, 'Registration changed player data'
blank = post('/api/Account/Authenticate', ['',1,None,None,'2.31.3'])
assert blank[0] and data(blank[0]) == baseline
assert not post('/api/Account/Authenticate', ['foreign-token',1,None,None,'2.31.3'])[0]
print('PASS: registration twice, registered-token login, empty-token login, unchanged player data, foreign-token rejection')
