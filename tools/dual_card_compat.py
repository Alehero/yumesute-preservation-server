"""Dual-idol cards: link the second idol's CharacterBase.

CharacterMaster rows with secondary_character_base_master_id feature two idols. The
pinned upstream grant (helpers.things._grant_character) only resolves the primary
idol, so such cards were saved with secondaryCharacterBaseId NULL and
secondarySenseLevel 0. The client cannot show those cards in a party: the edit
screen hangs after EditParty and the party page fails on the next login.

install() replaces the grant for new cards and, at startup, repairs saved cards.
"""
from contextlib import asynccontextmanager
from helpers.cache import cache


def dual_masters():
    """{character master id: secondary character base master id} for dual-idol cards."""
    return {
        m.id_: m.secondary_character_base_master_id
        for m in cache.character_master
        if m.secondary_character_base_master_id is not None
    }


async def owned_base(conn, user_id, base_master_id, character_master_id):
    """The id of the user's CharacterBase for base_master_id, created on first use."""
    from helpers.things import _by_id, _random_id
    from db.user.grant import create_character_base, get_character_base

    existing = await conn.fetchrow(get_character_base(user_id, base_master_id))
    if existing is not None:
        return existing.id
    base_id = _random_id()
    bm = _by_id("character_base_master").get(base_master_id)
    costume = bm.default_costume_master_id if bm is not None else None
    await conn.execute(create_character_base(user_id, base_id, base_master_id, costume, character_master_id))
    return base_id


async def grant_character(conn, user_id, character_master_id):
    """helpers.things._grant_character, plus the secondary idol for dual-idol cards."""
    from helpers.things import _by_id, _random_id

    master = _by_id("character_master").get(character_master_id)
    base_master_id = master.character_base_master_id if master is not None else None
    secondary_master_id = master.secondary_character_base_master_id if master is not None else None
    base_id = 0
    if base_master_id is not None:
        base_id = await owned_base(conn, user_id, base_master_id, character_master_id)
    secondary_id = None
    if secondary_master_id is not None:
        secondary_id = await owned_base(conn, user_id, secondary_master_id, character_master_id)
    await conn.conn.execute(
        'INSERT INTO "character" ("userId", "id", "characterMasterId", "characterBaseId", "level", '
        '"senseLevel", "secondaryCharacterBaseId", "secondarySenseLevel", "selectionType") '
        'VALUES ($1, $2, $3, $4, 1, 1, $5, $6, 1)',
        user_id, _random_id(), character_master_id, base_id, secondary_id,
        1 if secondary_id is not None else 0,
    )


async def repair_dual_cards(conn):
    """Link the second idol on saved dual-idol cards that are missing it. Returns the count."""
    duals = dual_masters()
    if not duals:
        return 0
    rows = await conn.conn.fetch(
        'SELECT "userId", "id", "characterMasterId" FROM "character" '
        'WHERE "secondaryCharacterBaseId" IS NULL AND "characterMasterId" = ANY($1::bigint[])',
        list(duals),
    )
    for row in rows:
        master_id = row["characterMasterId"]
        base_id = await owned_base(conn, row["userId"], duals[master_id], master_id)
        await conn.conn.execute(
            'UPDATE "character" SET "secondaryCharacterBaseId"=$3, '
            '"secondarySenseLevel"=GREATEST("secondarySenseLevel", 1) '
            'WHERE "userId"=$1 AND "id"=$2 AND "secondaryCharacterBaseId" IS NULL',
            row["userId"], row["id"], base_id,
        )
    return len(rows)


def install(app):
    import helpers.things
    helpers.things._grant_character = grant_character
    previous = app.router.lifespan_context

    @asynccontextmanager
    async def lifespan(app):
        async with previous(app):
            async with app.acquire_db() as conn, conn.transaction():
                repaired = await repair_dual_cards(conn)
            if repaired:
                print(f'Linked the second idol on {repaired} dual-idol card(s)', flush=True)
            yield

    app.router.lifespan_context = lifespan
