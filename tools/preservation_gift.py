"""Permanent local-preservation gift, issued once per account."""
import json
import time
from pathlib import Path
from fastapi import APIRouter, Request
from db.user import upsert_inbox, get_inboxes_by_ids, receive_inbox
from helpers.things import grant_thing, present_type
from helpers.user_data import build_present, current_user_id
from helpers.msgpack import respond
from models import InboxReceiveResult

ROOT = Path(__file__).resolve().parents[1]
EVENT = 'song-tickets-v1'
# Captured official no-time-limit Inbox sentinel; zero can be filtered as expired.
NO_EXPIRY = 4102358400000000

def quantity():
    value = json.loads((ROOT/'preservation-rules.json').read_text()).get('preservation_song_tickets', 10000)
    if type(value) is not int or not 0 <= value <= 1000000:
        raise ValueError('preservation_song_tickets must be an integer between 0 and 1000000')
    return value

async def ensure_gift(app, uid):
    count = quantity()
    if uid is None or not count:
        return
    async with app.acquire_db() as c, c.transaction():
        await c.conn.execute('SELECT pg_advisory_xact_lock(724610, $1::int)', uid)
        await c.conn.execute('CREATE TABLE IF NOT EXISTS preservation_gifts (user_id bigint, event text, inbox_id bigint, PRIMARY KEY(user_id,event))')
        existing = await c.conn.fetchval('SELECT inbox_id FROM preservation_gifts WHERE user_id=$1 AND event=$2',uid,EVENT)
        if existing is not None:
            await c.conn.execute('UPDATE inbox SET "receiveLimitAt"=$3, checked=false WHERE "userId"=$1 AND id=$2 AND NOT "hasReceived" AND "receiveLimitAt"=0',uid,existing,NO_EXPIRY)
            return
        if not await c.conn.fetchval('SELECT 1 FROM accounts WHERE "userId"=$1',uid):
            return
        inbox_id = await c.conn.fetchval('SELECT GREATEST(COALESCE(MAX(id),0)+1, 1900000000) FROM inbox WHERE "userId"=$1',uid)
        await c.execute(upsert_inbox(uid,dict(id=inbox_id,thingType=1,thingId=130001,thingQuantity=count,isTimeLimited=False,hasReceived=False,title='楽曲解放サポート',description='ローカル保存用プレゼント：歌劇目録',sentAt=int(time.time()*1000000),receivedAt=None,receiveLimitAt=NO_EXPIRY)))
        await c.conn.execute('INSERT INTO preservation_gifts VALUES ($1,$2,$3)',uid,EVENT,inbox_id)

async def receive(app, uid, inbox_ids):
    ids = list(dict.fromkeys(inbox_ids))
    result = InboxReceiveResult(received_things=[],has_not_receive_things=False)
    if uid is None or not ids:
        return respond(result)
    now = int(time.time()*1000000)
    types, received_ids = set(), set()
    async with app.acquire_db() as c, c.transaction():
        await c.conn.execute('SELECT pg_advisory_xact_lock(724610, $1::int)',uid)
        for row in await c.fetch(get_inboxes_by_ids(uid,ids)):
            if row.hasReceived:
                continue
            if row.isTimeLimited and row.receiveLimitAt and row.receiveLimitAt < now:
                result.has_not_receive_things=True
                continue
            result.received_things.append(await grant_thing(c,uid,row.thingType,row.thingId,row.thingQuantity))
            await c.execute(receive_inbox(uid,row.id,now))
            received_ids.add(row.id)
            pt=present_type(row.thingType)
            if pt: types.add(pt)
    if 'Currency' in types: types.add('User')
    return respond(result,present=await build_present(app,uid,*types,('Inbox',received_ids)))

def install(app):
    import routes.inbox
    routes.inbox._receive = receive
    router = APIRouter()
    @router.post('/api/Inboxes/CheckPackagesAsync')
    async def check(request: Request):
        await ensure_gift(request.app,current_user_id(request))
        return await routes.inbox.inbox_check_packages(request)
    app.router.routes[0:0] = router.routes
