"""Persist music bookmark changes instead of accepting them as no-op requests."""

from fastapi import APIRouter, Request

from db.user import upsert_music_bookmark
from helpers.msgpack import read_request, respond
from helpers.cache import cache
from helpers.user_data import current_user_id, data_object
from models import BooleanResult, EditBookmarkPayload
from models.database import MusicBookmarkModel


router = APIRouter(tags=["Music bookmark compatibility"])


@router.post("/api/Lives/Music/EditBookmark", name="Lives_EditBookmark")
async def edit_music_bookmark(request: Request):
    user_id = current_user_id(request)
    payload = await read_request(request, EditBookmarkPayload)
    if user_id is None or payload is None or payload.music_master_id <= 0:
        return respond(BooleanResult())

    music_id = payload.music_master_id
    bookmark_flag = int(payload.bookmark_flag)
    # The enum permits unknown integers; only the three bookmark bits are valid.
    if bookmark_flag < 0 or bookmark_flag & ~7 or not any(
        music.id_ == music_id for music in cache.music_master
    ):
        return respond(BooleanResult())
    app = request.app
    async with app.acquire_db() as conn:
        async with conn.conn.transaction():
            # The upstream table has no unique constraint on a music ID. Serialize
            # edits for this account/song pair so repeated taps cannot add duplicates.
            await conn.conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended($1, 0))",
                f"music-bookmark:{user_id}:{music_id}",
            )
            existing = await conn.conn.fetchrow(
                'SELECT "rowId" FROM "music_bookmark" '
                'WHERE "userId"=$1 AND "musicMasterId"=$2 '
                'ORDER BY "rowId" LIMIT 1',
                user_id,
                music_id,
            )
            if existing is None:
                if bookmark_flag != 0:
                    await conn.execute(
                        upsert_music_bookmark(
                            user_id,
                            {
                                "musicMasterId": music_id,
                                "musicBookmarkFlag": bookmark_flag,
                            },
                        )
                    )
            else:
                await conn.conn.execute(
                    'UPDATE "music_bookmark" SET "musicBookmarkFlag"=$3 '
                    'WHERE "userId"=$1 AND "musicMasterId"=$2',
                    user_id,
                    music_id,
                    bookmark_flag,
                )
                await conn.conn.execute(
                    'DELETE FROM "music_bookmark" WHERE "userId"=$1 '
                    'AND "musicMasterId"=$2 AND "rowId"<>$3',
                    user_id,
                    music_id,
                    existing["rowId"],
                )

    result = BooleanResult(is_success=True)
    if existing is None and bookmark_flag == 0:
        return respond(result)
    return respond(
        result,
        present=[
            data_object(
                "MusicBookmark",
                MusicBookmarkModel(
                    userId=user_id,
                    musicMasterId=music_id,
                    musicBookmarkFlag=bookmark_flag,
                ),
            )
        ],
    )


def install(app):
    """Register ahead of the upstream route, which currently only returns success."""
    app.router.routes[0:0] = list(router.routes)
