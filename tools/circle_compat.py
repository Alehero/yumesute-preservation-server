"""Safe single-account circle responses for the local preservation server.

This installation has no circle/community persistence or peer accounts. Returning
default placeholder circle rows makes the client treat an invalid row as a real
circle, so the read-only discovery endpoints report empty collections instead.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Request

from helpers.msgpack import read_request, respond
from helpers.user_data import current_user_id
from models import (
    CircleInformationResult,
    CircleMemberInfoResult,
    CircleResultStatus,
    MyCircleInformationResult,
    RawRankingResult,
    SupportCompanyInformation,
    SupportCompanyLevelLimitStatus,
    SupportCompanyLevelStatus,
)


router = APIRouter()


def _not_found_circle():
    return CircleInformationResult(result_status=CircleResultStatus.DataNotFound)


@router.get("/api/Circles")
async def get_circles(request: Request):
    return respond([])


@router.get("/api/Circles/Invited")
async def get_invited_circles(request: Request):
    return respond([])


@router.get("/api/Circles/Search")
async def search_circles(request: Request, circleName: str | None = None):
    return respond([])


@router.post("/api/Circles/Condition")
async def search_circles_by_condition(request: Request):
    # Consume and validate the request just as the upstream route does.
    from models import CirclePayload

    await read_request(request, CirclePayload)
    return respond([])


@router.post("/api/Circles")
async def get_circle(request: Request, circleId: str | None = None):
    return respond(_not_found_circle())


@router.get("/api/Circles/MemberInfo")
async def get_circle_members(request: Request, circleId: str | None = None):
    return respond(
        CircleMemberInfoResult(
            parameters=[], result_status=CircleResultStatus.DataNotFound
        )
    )


@router.post("/api/Circles/MyCircleInfo")
async def get_my_circle(request: Request):
    return respond(
        MyCircleInformationResult(
            result_status=CircleResultStatus.DataNotFound,
            support_company_information=await _support_information(request),
        )
    )


def _timestamp(value):
    if value is None or value <= 0:
        return ""
    # circle_support stores Unix milliseconds.
    return datetime.fromtimestamp(value / 1000, timezone.utc).isoformat().replace(
        "+00:00", "Z"
    )


async def _support_information(request: Request):
    uid = current_user_id(request)
    app = request.app
    async with app.acquire_db() as conn:
        rows = await conn.conn.fetch(
            'SELECT company, level, "currentSupportPoint", '
            '"lastLevelUppedAt", "levelLimit" FROM circle_support '
            'WHERE "userId"=$1',
            uid,
        )
    by_company = {row["company"]: row for row in rows}

    def status(company):
        row = by_company.get(company)
        return SupportCompanyLevelStatus(
            level=row["level"] if row else 0,
            current_support_point=row["currentSupportPoint"] if row else 0,
            last_level_upped_at=_timestamp(row["lastLevelUppedAt"]) if row else "",
            level_limit=row["levelLimit"] if row else 0,
            # An empty list is the correct shape when no limit items are stored.
            level_limit_status=SupportCompanyLevelLimitStatus(
                current_coin_quantity=0, details=[]
            ),
        )

    return SupportCompanyInformation(
        sirius=status(1), eden=status(2), gingaza=status(3), denki=status(4)
    )


@router.get("/api/Circles/GetSupportAndTheaterLevelInformation")
async def get_support_and_theater_levels(request: Request):
    return respond(await _support_information(request))


@router.get("/api/Circles/Ranking/Daily")
@router.get("/api/Circles/Ranking/Weekly")
@router.get("/api/Circles/Ranking/Monthly")
async def get_support_ranking(request: Request):
    return respond(RawRankingResult(raw_ranking=[], user_profiles=[]))


def install(app):
    """Place these compatibility handlers before upstream placeholder routes."""
    app.router.routes[0:0] = list(router.routes)
