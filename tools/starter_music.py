"""Keep one chart selectable when a device remembers STELLA or OLIVIER."""
STARTER_MUSIC_ID = 244  # Default song; Olivier level 101 (I) in the pinned master.

async def grant_starter_music(conn, uid):
    # Serialize with another login without depending on a per-song unique index.
    await conn.conn.fetchval('SELECT "userId" FROM accounts WHERE "userId"=$1 FOR UPDATE', uid)
    exists = await conn.conn.fetchval('SELECT id FROM music WHERE "userId"=$1 AND "musicMasterId"=$2', uid, STARTER_MUSIC_ID)
    if exists is None:
        await conn.conn.execute('INSERT INTO music ("userId",id,"musicMasterId","stellaReleased","vocalVersion","olivierReleaseStatus","isPossession") SELECT $1,COALESCE(MAX(id),0)+1,$2,true,0,3,true FROM music WHERE "userId"=$1', uid, STARTER_MUSIC_ID)
    else:
        await conn.conn.execute('UPDATE music SET "isPossession"=true,"stellaReleased"=true,"olivierReleaseStatus"=3 WHERE "userId"=$1 AND "musicMasterId"=$2', uid, STARTER_MUSIC_ID)

async def ensure_starter_music(app, uid, account):
    if account.get('mode') != 'fresh' or uid != account.get('user_id'):
        return
    async with app.acquire_db() as conn, conn.transaction():
        await grant_starter_music(conn, uid)
