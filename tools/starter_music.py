"""Keep one chart selectable when a device remembers STELLA or OLIVIER."""
STARTER_MUSIC_ID = 244  # Default song; Olivier level 101 (I) in the pinned master.

async def grant_default_music(conn, uid):
    # Serialize with another login without depending on a per-song unique index.
    await conn.conn.fetchval('SELECT "userId" FROM accounts WHERE "userId"=$1 FOR UPDATE', uid)
    from helpers.cache import cache
    from helpers.music_unlock import granted_music_state
    # The client treats these as owned without a Music row; progression needs rows.
    for master in cache.music_master:
        if int(master.unlock_condition_type) != 1 or master.invisible or master.id_ == 9999:
            continue
        present = await conn.conn.fetchval('SELECT id FROM music WHERE "userId"=$1 AND "musicMasterId"=$2', uid, master.id_)
        if present is None:
            stella, olivier = await granted_music_state(conn, uid, master.id_)
            await conn.conn.execute('INSERT INTO music ("userId",id,"musicMasterId","stellaReleased","vocalVersion","olivierReleaseStatus","isPossession") SELECT $1,COALESCE(MAX(id),0)+1,$2,$3,0,$4,true FROM music WHERE "userId"=$1', uid, master.id_, stella, olivier)

async def grant_starter_music(conn, uid):
    await grant_default_music(conn, uid)
    exists = await conn.conn.fetchval('SELECT id FROM music WHERE "userId"=$1 AND "musicMasterId"=$2', uid, STARTER_MUSIC_ID)
    if exists is None:
        await conn.conn.execute('INSERT INTO music ("userId",id,"musicMasterId","stellaReleased","vocalVersion","olivierReleaseStatus","isPossession") SELECT $1,COALESCE(MAX(id),0)+1,$2,true,0,3,true FROM music WHERE "userId"=$1', uid, STARTER_MUSIC_ID)
    else:
        await conn.conn.execute('UPDATE music SET "isPossession"=true,"stellaReleased"=true,"olivierReleaseStatus"=3 WHERE "userId"=$1 AND "musicMasterId"=$2', uid, STARTER_MUSIC_ID)

async def ensure_starter_music(app, uid, account):
    async with app.acquire_db() as conn, conn.transaction():
        if account.get('mode') == 'fresh' and uid == account.get('user_id'):
            await grant_starter_music(conn, uid)
        else:
            # Imported saves may omit implicit default-song ownership too.
            # Materialize only missing defaults; no starter difficulty grant.
            await grant_default_music(conn, uid)
