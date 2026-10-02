"""Read-only verification of every pinned supplemental file on localhost:8125."""
import asyncio,hashlib,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import httpx
from supplemental_resources import resources

async def main():
    sem=asyncio.Semaphore(8)
    async with httpx.AsyncClient(base_url='http://127.0.0.1:8125',timeout=30,follow_redirects=False) as client:
        async def check(entry):
            async with sem:
                response=await client.get(entry['url_path'])
                assert response.status_code==200,entry['url_path']
                assert hashlib.sha256(response.content).hexdigest()==entry['sha256'],entry['url_path']
        await asyncio.gather(*(check(e) for e in resources().values()))
        missing=await client.get('/production/static-assets/Resources/Textures/absent-preservation-test.png')
        assert missing.status_code==404 and 'location' not in missing.headers
    print(f'PASS: {len(resources())} local HTTP resources match pinned checksums; missing static resource returns 404 without redirect.')

if __name__=='__main__':asyncio.run(main())
