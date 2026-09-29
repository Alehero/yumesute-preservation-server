"""API smoke check against a running LOCAL test installation.
Run from the repository root: uv run --locked python tests/check_running.py
Uses this installation's private credentials; does not print tokens or account data.
"""
import json,sys
from pathlib import Path
import httpx,msgpack
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from protocol import envelope

def main():
    state=json.loads((ROOT/'private/account.json').read_text())
    text=(ROOT/'private/linking-credentials.txt').read_text().splitlines()
    password=text[2].split(': ',1)[1]
    base='http://127.0.0.1:8125'
    def post(path,data):
        r=httpx.post(base+path,content=msgpack.packb(data),timeout=30);r.raise_for_status();return envelope(r.content)[1]
    assert post('/api/Account/GetTakeOverAccount',[state['transfer']['code'],'wrong'])[0] is False
    linked=post('/api/Account/GetTakeOverAccount',[state['transfer']['code'],password]);assert linked[0] and linked[4]
    auth=post('/api/Account/Authenticate',[linked[4],1,None,None,'2.31.3']);assert auth[0]
    r=httpx.get(base+'/api/data/user',headers={'Authorization':'Bearer '+auth[0]},timeout=30);r.raise_for_status()
    entities=envelope(r.content)[1];assert isinstance(entities,list) and any(x and x[0]==0 and x[1][0]==state['user_id'] for x in entities)
    assert post('/api/Environment?applicationVersion=2.31.3&gameVersion=1',[])[0]=='2.31.3'
    r=httpx.get(base+'/master-data/production/preservation/mastermemory_test.db',timeout=30);assert r.status_code==200 and len(r.content)>1000
    assert httpx.get(base+'/production/Notations/does-not-exist/missing.enc').status_code==404
    print('PASS: wrong-password rejection, linking, authentication, account data, Environment, master data, missing-asset 404')
if __name__=='__main__':main()
