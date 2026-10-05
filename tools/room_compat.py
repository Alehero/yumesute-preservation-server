"""Safe responses for multiplayer room discovery on the local server."""

from fastapi import APIRouter

from helpers.msgpack import respond


router = APIRouter()


@router.get("/api/MultiRooms")
async def get_multi_rooms():
    # This server does not host multiplayer rooms. Return an empty collection
    # instead of exposing the upstream handler's invalid placeholder room.
    return respond([])


def install(app):
    """Register before upstream routes so the empty list takes precedence."""
    app.router.routes[0:0] = list(router.routes)
