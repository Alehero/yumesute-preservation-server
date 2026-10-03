"""Preservation implementations for actions verified against the September 2026 captures.

Installed as route replacements; no modifications to the pinned upstream checkout.
All mutations are atomic and serialized per account. Master data supplies costs/limits.
"""

from collections import Counter
from contextlib import asynccontextmanager
import math
import struct

from fastapi import APIRouter, Request
from helpers.cache import cache
from helpers.user_data import current_user_id, _table, _to_array
from helpers.msgpack import respond
from helpers.character_enhance import (
    character_master,
    sense_enhance_cost,
    max_sense_level,
    max_talent_stage,
    bloom_rewards,
)
from helpers.character_level import experience_item
from helpers.things import grant_things_consolidated
from helpers.episodes import (
    episode_read_reward_things,
    episode_readall_reward_things,
    episode_result,
    _local_meta,
)
from models import BooleanResult, StarPointResult, UseExperienceItemsPayload
from models.unions import IDATA_OBJECT_KEY
from db import user as queries

router = APIRouter()


class Rejected(Exception):
    pass


def master(table, ident, field="id_"):
    return next((x for x in getattr(cache, table) if getattr(x, field) == ident), None)


def f32(value):
    return struct.unpack("<f", struct.pack("<f", value))[0]


class State:
    def __init__(self, conn, uid):
        self.conn, self.uid = conn, uid
        self.tables = {}
        self.dirty = {}

    async def rows(self, name):
        if name not in self.tables:
            # Table names originate solely from the implementation, never the request.
            self.tables[name] = [
                dict(x)
                for x in await self.conn.conn.fetch(
                    f'SELECT * FROM "{_table(name)}" WHERE "userId"=$1', self.uid
                )
            ]
        return self.tables[name]

    async def one(self, name, **where):
        return next(
            (
                r
                for r in await self.rows(name)
                if all(r.get(k) == v for k, v in where.items())
            ),
            None,
        )

    @staticmethod
    def key_field(name):
        return {"Episode": "episodeMasterId", "ConcertStage": "concertStageMasterId", "HomeBGM": "homeBGMMasterId", "CharacterLesson": "characterBaseMasterId"}.get(name, "id")

    async def update(self, entity, row, **values):
        if row is None:
            raise Rejected("Missing account record")
        if not values:
            return
        pk = self.key_field(entity)
        columns = ", ".join(f'"{k}"=${i + 3}' for i, k in enumerate(values))
        await self.conn.conn.execute(
            f'UPDATE "{_table(entity)}" SET {columns} WHERE "userId"=$1 AND "{pk}"=$2',
            self.uid,
            row[pk],
            *values.values(),
        )
        row.update(values)
        self.dirty[(entity, row[self.key_field(entity)])] = row.copy()

    async def insert(self, entity, **values):
        rows = await self.rows(entity)
        pk = self.key_field(entity)
        if pk == "id":
            values.setdefault("id", max([r["id"] for r in rows] + [0]) + 1)
        q = getattr(queries, "upsert_" + _table(entity))(self.uid, values)
        await self.conn.execute(q)
        row = dict(
            await self.conn.conn.fetchrow(
                f'SELECT * FROM "{_table(entity)}" WHERE "userId"=$1 AND "{pk}"=$2',
                self.uid,
                values[pk],
            )
        )
        rows.append(row)
        self.dirty[(entity, row[self.key_field(entity)])] = row.copy()
        return row

    async def pay(self, costs, coin=0):
        if coin < 0 or any(n < 0 for n in costs.values()):
            raise Rejected("Invalid cost")
        items = {r["itemMasterId"]: r for r in await self.rows("Item")}
        currency = await self.one("Currency")
        if any(items.get(i, {}).get("stock", 0) < n for i, n in costs.items()) or (
            coin and (not currency or currency["coin"] < coin)
        ):
            raise Rejected("Insufficient resources")
        for i, n in costs.items():
            if n:
                await self.update("Item", items[i], stock=items[i]["stock"] - n)
        if coin:
            await self.update("Currency", currency, coin=currency["coin"] - coin)

    async def grant(self, things):
        if not things:
            return []
        from helpers.things import present_type

        names = {present_type(t) for t, _, _ in things} - {None}
        snapshots = {
            name: {r["id"]: r.copy() for r in await self.rows(name)} for name in names
        }
        result = await grant_things_consolidated(self.conn, self.uid, things)
        # Grant helpers can create multiple resource types, reload just the affected rows.
        from helpers.things import present_type

        for name in names:
            before = snapshots[name]
            self.tables.pop(name, None)
            for row in await self.rows(name):
                if before.get(row["id"]) != row:
                    self.dirty[(name, row[self.key_field(name)])] = row.copy()
        return result

    def present(self):
        return [
            [IDATA_OBJECT_KEY[n], _to_array(n, r)] for (n, _), r in self.dirty.items()
        ]


@asynccontextmanager
async def transaction(request):
    uid = current_user_id(request)
    if uid is None:
        raise Rejected("Authentication required")
    async with request.app.acquire_db() as conn, conn.transaction():
        await conn.conn.execute("SELECT pg_advisory_xact_lock($1)", uid)
        yield State(conn, uid)


async def character_progress(s, base, mission_id, delta):
    if delta <= 0:
        return
    m = master("character_mission_master", mission_id)
    stages = sorted(m.stages or [], key=lambda x: x.stage_order)
    row = await s.one(
        "CharacterMission",
        characterBaseMasterId=base,
        characterMissionMasterId=mission_id,
    )
    count = (row["currentCount"] if row else 0) + delta
    cleared = max([x.stage_order for x in stages if x.goal_count <= count] + [0])
    if row:
        await s.update(
            "CharacterMission",
            row,
            currentCount=count,
            clearedStageOrder=max(cleared, row["clearedStageOrder"]),
        )
    else:
        await s.insert(
            "CharacterMission",
            characterBaseMasterId=base,
            characterMissionMasterId=mission_id,
            currentStageMasterId=stages[0].id_,
            currentCount=count,
            clearedStageOrder=cleared,
            rewardReceivedStageOrder=0,
            completedLevel=0,
        )


async def mission_progress(s, ident, delta=1, *, create=False, absolute=None):
    m = master("mission_master", ident)
    if not m or not m.stages:
        return
    row = await s.one("Mission", missionMasterId=ident)
    if not row and not create:
        return
    stage = next(
        (x for x in m.stages if row and x.id_ == row["currentMissionStageMasterId"]),
        m.stages[0],
    )
    old = row["missionCurrentCount"] if row else 0
    count = max(old, absolute) if absolute is not None else old + delta
    cleared = count >= stage.stage_goal_value
    newly = cleared and (not row or not row["isCleared"])
    if row:
        await s.update(
            "Mission",
            row,
            missionCurrentCount=count,
            isCleared=row["isCleared"] or cleared,
        )
    else:
        await s.insert(
            "Mission",
            missionMasterId=ident,
            currentMissionStageMasterId=stage.id_,
            missionCurrentCount=count,
            isCleared=cleared,
            isRewardReceived=False,
        )
    if newly and 1 <= ident < 42:
        await mission_progress(s, 42)
        if ident % 6:
            await mission_progress(s, ((ident - 1) // 6 + 1) * 6)


async def receive_missions(request, mission_id=None, category=None):
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)

    def available(value, end=False):
        if not value:
            return True
        date = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return now < date if end else date <= now

    try:
        async with transaction(request) as s:
            rewards = []
            for row in await s.rows("Mission"):
                m = master("mission_master", row["missionMasterId"])
                if (
                    not m
                    or (mission_id is not None and m.id_ != mission_id)
                    or (category is not None and int(m.mission_category) != category)
                    or row["isRewardReceived"]
                    or not row["isCleared"]
                    or not available(m.start_date)
                    or not available(m.end_date, end=True)
                ):
                    continue
                stages = sorted(m.stages or [], key=lambda x: x.mission_stage_order)
                stage = next(
                    (x for x in stages if x.id_ == row["currentMissionStageMasterId"]),
                    None,
                )
                if (
                    not stage
                    or row["missionCurrentCount"] < stage.stage_goal_value
                    or not available(stage.start_date)
                ):
                    continue
                rewards.extend(
                    (int(r.thing_type), r.thing_id, r.thing_quantity)
                    for r in stage.rewards or []
                )
                following = next(
                    (
                        x
                        for x in stages
                        if x.mission_stage_order > stage.mission_stage_order
                    ),
                    None,
                )
                if following:
                    await s.update(
                        "Mission",
                        row,
                        currentMissionStageMasterId=following.id_,
                        isCleared=row["missionCurrentCount"]
                        >= following.stage_goal_value,
                        isRewardReceived=False,
                    )
                else:
                    await s.update("Mission", row, isRewardReceived=True)
            received = await s.grant(rewards)
        return respond(received, present=s.present())
    except Rejected:
        return respond([])


@router.post("/api/Missions/{missionId}/receiveCurrentRewards")
async def mission_claim(request: Request, missionId: int):
    return await receive_missions(request, mission_id=missionId)


@router.post("/api/Missions/receiveRewards")
async def mission_claim_category(request: Request, missionCategory: int):
    return await receive_missions(request, category=missionCategory)


async def level_missions(s, cm, delta, level):
    if delta <= 0:
        return
    base = master("character_base_master", cm.character_base_master_id)
    await character_progress(s, cm.character_base_master_id, 3, delta)
    await mission_progress(s, 1200, delta)
    if base:
        await mission_progress(s, base.company_master_id * 100 + 20, delta)
    for mid in (300030, 300100):
        await mission_progress(s, mid, delta)
    if level >= 10:
        await mission_progress(s, 8, absolute=1, create=True)


@router.post("/api/Accessories/{uAccessoryId}/LevelUp/{levelTo}")
async def accessory_level(request: Request, uAccessoryId: int, levelTo: int):
    try:
        async with transaction(request) as s:
            row = await s.one("Accessory", id=uAccessoryId)
            if not row:
                raise Rejected()
            m = master("accessory_master", row["accessoryMasterId"])
            if not m or not row["level"] < levelTo <= m.max_level:
                raise Rejected()
            group = master(
                "accessory_level_pattern_group_master",
                m.accessory_level_pattern_group_id,
            )
            costs = Counter()
            coin = 0
            for lv in range(row["level"], levelTo):
                step = next((p for p in group.patterns if p.level == lv), None)
                if not step:
                    raise Rejected()
                coin += step.required_coin
                for i in step.items or []:
                    costs[i.item_master_id] += i.quantity
            await s.pay(costs, coin)
            await s.update("Accessory", row, level=levelTo)
        return respond(BooleanResult(is_success=True), present=s.present())
    except Rejected:
        return respond(BooleanResult())


@router.post("/api/Posters/{uPosterId}/LevelUp/{levelTo}")
async def poster_level(request: Request, uPosterId: int, levelTo: int):
    try:
        async with transaction(request) as s:
            row = await s.one("Poster", id=uPosterId)
            if not row:
                raise Rejected()
            m = master("poster_master", row["posterMasterId"])
            group = (
                master(
                    "poster_level_pattern_group_master", m.level_pattern_group_master_id
                )
                if m
                else None
            )
            if (
                not group
                or not row["level"]
                < levelTo
                <= max(p.level for p in group.patterns) + 1
            ):
                raise Rejected()
            costs = Counter()
            delta = levelTo - row["level"]
            for lv in range(row["level"], levelTo):
                steps = [p for p in group.patterns if p.level == lv]
                if not steps:
                    raise Rejected()
                for p in steps:
                    costs[p.item_master_id] += p.quantity
            await s.pay(costs)
            await s.update("Poster", row, level=levelTo)
            bonus = await s.one("UserBonus")
            await s.update(
                "UserBonus",
                bonus,
                lessonStarRankBonus=f32(bonus["lessonStarRankBonus"] + 0.1 * delta),
            )
            await mission_progress(s, 1300, delta)
            for mid in (300010, 300090):
                await mission_progress(s, mid, delta)
            if levelTo >= 2:
                await mission_progress(s, 15, create=True, absolute=1)
        return respond(BooleanResult(is_success=True), present=s.present())
    except Rejected:
        return respond(BooleanResult())


@router.post("/api/Posters/{uPosterId}/Breakthrough/{phaseTo}")
async def poster_breakthrough(request: Request, uPosterId: int, phaseTo: int):
    try:
        async with transaction(request) as s:
            row = await s.one("Poster", id=uPosterId)
            if not row:
                raise Rejected()
            m = master("poster_master", row["posterMasterId"])
            group = (
                master("poster_release_item_group_master", m.release_item_group_id)
                if m
                else None
            )
            if (
                not group
                or m.is_restrict_item_break_through
                or phaseTo <= row["breakthroughPhase"]
            ):
                raise Rejected()
            max_phase = (
                m.poster_breakthrough_max_phase
                or max(i.current_phase for i in group.items) + 1
            )
            from helpers.character_level import started
            from datetime import datetime, timezone

            if m.poster_breakthrough_max_phase_release_date and not started(
                m.poster_breakthrough_max_phase_release_date, datetime.now(timezone.utc)
            ):
                max_phase -= 1
            if phaseTo > max_phase:
                raise Rejected()
            costs = Counter()
            delta = phaseTo - row["breakthroughPhase"]
            for offset, phase in enumerate(range(row["breakthroughPhase"], phaseTo)):
                index = (
                    row["itemConsumeBreakThroughCount"] + offset
                    if group.item_consume_apply_flag
                    else phase
                )
                steps = [i for i in group.items if i.current_phase == index]
                if not steps:
                    raise Rejected()
                for i in steps:
                    costs[i.item_master_id] += i.required_quantity
            await s.pay(costs)
            await s.update(
                "Poster",
                row,
                breakthroughPhase=phaseTo,
                itemConsumeBreakThroughCount=row["itemConsumeBreakThroughCount"]
                + delta,
            )
        return respond(BooleanResult(is_success=True), present=s.present())
    except Rejected:
        return respond(BooleanResult())


@router.post("/api/Characters/{characterMasterId}/ReleaseSideStory")
async def release_story(request: Request, characterMasterId: int, order: int = 1):
    try:
        async with transaction(request) as s:
            row = await s.one("Character", characterMasterId=characterMasterId)
            cm = character_master(characterMasterId)
            episode = next(
                (
                    e
                    for e in cache.character_episode_master
                    if e.character_master_id == characterMasterId
                    and int(e.episode_order) == order
                ),
                None,
            )
            if (
                not row
                or not episode
                or row["level"] < episode.required_character_level
                or order != row["releasedEpisodeOrder"] + 1
            ):
                raise Rejected()
            gid = (
                cm.first_episode_release_item_group_id
                if order == 1
                else cm.second_episode_release_item_group_id
            )
            group = master("character_episode_release_item_group_master", gid)
            if not group:
                raise Rejected()
            costs = Counter()
            for i in group.items or []:
                if i.order == order:
                    costs[i.item_master_id] += i.required_quantity
            if not costs:
                raise Rejected()
            await s.pay(costs)
            await s.update("Character", row, releasedEpisodeOrder=order)
        return respond(BooleanResult(is_success=True), present=s.present())
    except Rejected:
        return respond(BooleanResult())


@router.post("/api/Posters/{uPosterId}/UpdateReleasedPosterStory/{posterEpisodeType}")
async def poster_story(request: Request, uPosterId: int, posterEpisodeType: str):
    from models.enums import PosterEpisodeTypes

    try:
        try:
            episode = int(PosterEpisodeTypes[posterEpisodeType])
        except KeyError:
            episode = int(PosterEpisodeTypes(int(posterEpisodeType)))
        async with transaction(request) as s:
            row = await s.one("Poster", id=uPosterId)
            if not row:
                raise Rejected()
            available = {
                int(x.episode_type)
                for x in cache.poster_story_master
                if x.poster_master_id == row["posterMasterId"]
            }
            if episode not in available or episode <= row["releasedEpisode"]:
                raise Rejected()
            # Preservation behavior: record the requested existing chapter. Exact
            # official unlock requirements have not yet been captured; do not
            # invent a resource charge from the poster breakthrough cost table.
            count = sum(row["releasedEpisode"] < e <= episode for e in available)
            await s.update("Poster", row, releasedEpisode=episode)
            pm = master("poster_master", row["posterMasterId"])
            for base in set(pm.appearance_character_base_master_ids or []):
                await character_progress(s, base, 8, count)
        return respond(BooleanResult(is_success=True), present=s.present())
    except (Rejected, ValueError):
        return respond(BooleanResult())


@router.post("/api/Episodes/{episodeMasterId}/GetDetails")
async def story_details(request: Request, episodeMasterId: int):
    from pathlib import Path
    import json
    from models import EpisodeResult

    manifest = (
        Path(__file__).resolve().parents[1] / "private/upstream/episode-manifest.json"
    )
    captured = (
        json.loads(manifest.read_text()).get(str(episodeMasterId))
        if manifest.exists()
        else None
    )
    if captured:
        return respond(EpisodeResult(**captured))
    result = episode_result(episodeMasterId)
    metadata = _local_meta(episodeMasterId)
    if result and metadata:
        result.episode_title, result.episode_order, result.story_type = metadata
    from models import EpisodeResult

    return respond(result or EpisodeResult())


async def read_story(request, eid, read_all):
    try:
        async with transaction(request) as s:
            relation = next(
                (
                    e
                    for e in cache.character_episode_master
                    if e.episode_master_id == eid
                ),
                None,
            )
            char = None
            if relation:
                char = await s.one(
                    "Character", characterMasterId=relation.character_master_id
                )
                if not char or char["releasedEpisodeOrder"] < int(
                    relation.episode_order
                ):
                    raise Rejected()
            existing = await s.one("Episode", episodeMasterId=eid)
            rewards = []
            if not existing:
                rewards += episode_read_reward_things(eid)
                if read_all:
                    rewards += episode_readall_reward_things(eid)
                await s.insert(
                    "Episode", id=eid, episodeMasterId=eid, hasReadAll=read_all
                )
                if char:
                    order = max(char["readEpisodeOrder"], int(relation.episode_order))
                    await s.update("Character", char, readEpisodeOrder=order)
                    cm = character_master(relation.character_master_id)
                    await character_progress(s, cm.character_base_master_id, 4, 1)
            elif read_all and not existing["hasReadAll"]:
                rewards += episode_readall_reward_things(eid)
                await s.update("Episode", existing, hasReadAll=True)
            result = await s.grant(rewards)
        return respond(result, present=s.present())
    except Rejected:
        return respond([])


@router.post("/api/Episodes/{episodeMasterId}/Read")
async def story_read(request: Request, episodeMasterId: int):
    return await read_story(request, episodeMasterId, False)


@router.post("/api/Episodes/{episodeMasterId}/ReadAll")
async def story_read_all(request: Request, episodeMasterId: int):
    return await read_story(request, episodeMasterId, True)


@router.post("/api/Characters/{characterId}/EnhanceSenseLevel/{levelTo}")
async def sense_level(
    request: Request, characterId: int, levelTo: int, priority: int = 1
):
    try:
        async with transaction(request) as s:
            row = await s.one("Character", id=characterId)
            if not row or priority not in (1, 2):
                raise Rejected()
            cm = character_master(row["characterMasterId"])
            field = "senseLevel" if priority == 1 else "secondarySenseLevel"
            base = (
                cm.character_base_master_id
                if priority == 1
                else cm.secondary_character_base_master_id
            )
            if not base or not row[field] < levelTo <= max_sense_level(cm):
                raise Rejected()
            costs = sense_enhance_cost(cm, row[field], levelTo)
            if not costs:
                raise Rejected()
            delta = levelTo - row[field]
            await s.pay(costs)
            await s.update("Character", row, **{field: levelTo})
            await character_progress(s, base, 5, delta)
            if levelTo >= 2:
                await mission_progress(s, 14, create=True, absolute=1)
        return respond(BooleanResult(is_success=True), present=s.present())
    except Rejected:
        return respond(BooleanResult())


@router.post("/api/Characters/{characterId}/BloomTalent/{stageTo}")
async def talent_bloom(request: Request, characterId: int, stageTo: int):
    try:
        async with transaction(request) as s:
            row = await s.one("Character", id=characterId)
            if not row:
                raise Rejected()
            cm = character_master(row["characterMasterId"])
            if not cm or not row["talentStage"] < stageTo <= max_talent_stage(cm):
                raise Rejected()
            stock = {r["itemMasterId"]: r["stock"] for r in await s.rows("Item")}
            # Generic pieces are a direct substitute when blooming (the exchange-shop
            # price in CharacterPieceMaster is not a bloom conversion multiplier).
            from helpers.character_enhance import _bloom_step, _piece

            costs = Counter()
            remaining = stock.copy()
            for stage in range(row["talentStage"], stageTo):
                step = _bloom_step(cm.rarity, stage)
                piece = _piece(cm.id_, step.talent_bloom_item_type)
                own = min(
                    remaining.get(piece.item_master_id, 0), step.required_piece_amount
                )
                costs[piece.item_master_id] += own
                remaining[piece.item_master_id] = (
                    remaining.get(piece.item_master_id, 0) - own
                )
                short = step.required_piece_amount - own
                if short:
                    from helpers.character_enhance import _generic_piece

                    generic, _ = _generic_piece(cm, step, piece)
                    if not generic or cm.forbid_generic_item_bloom:
                        raise Rejected()
                    costs[generic] += short
                if step.required_item_master_id:
                    costs[step.required_item_master_id] += (
                        step.required_item_amount or 0
                    )
            await s.pay(costs)
            delta = stageTo - row["talentStage"]
            rewards = bloom_rewards(cm, row["talentStage"], stageTo)
            await s.update("Character", row, talentStage=stageTo)
            await s.grant(rewards)
            await character_progress(s, cm.character_base_master_id, 6, delta)
        return respond(BooleanResult(is_success=True), present=s.present())
    except Rejected:
        return respond(BooleanResult())


@router.post("/api/CharacterMissions/{mCharacterBaseId}/receiveAllMission")
async def claim_star_rewards(request: Request, mCharacterBaseId: int):
    try:
        async with transaction(request) as s:
            base = await s.one("CharacterBase", characterBaseMasterId=mCharacterBaseId)
            if not base:
                raise Rejected()
            rank_before = base["starRank"]
            points_before = base["totalStarPoint"]
            points = 0
            categories = {
                x.id_: x for x in cache.character_mission_category_level_master
            }
            all_stages = [
                st for m in cache.character_mission_master for st in m.stages or []
            ]
            sizes = Counter(
                st.character_mission_category_level_master_id for st in all_stages
            )
            for row in await s.rows("CharacterMission"):
                if row["characterBaseMasterId"] != mCharacterBaseId:
                    continue
                m = master("character_mission_master", row["characterMissionMasterId"])
                stages = sorted(m.stages or [], key=lambda st: st.stage_order)
                available = [
                    st
                    for st in stages
                    if categories[st.character_mission_category_level_master_id].level
                    <= base["keyMissionLevel"] + 1
                ]
                pending = [
                    st
                    for st in available
                    if row["rewardReceivedStageOrder"]
                    < st.stage_order
                    <= row["clearedStageOrder"]
                ]
                if not pending:
                    continue
                for st in pending:
                    cid = st.character_mission_category_level_master_id
                    points += categories[cid].give_star_point // sizes[cid]
                claimed = max(st.stage_order for st in pending)
                # A completed category stays at its last stage until its next level is unlocked.
                current = next(
                    (st for st in available if st.stage_order > claimed), available[-1]
                )
                completed = max(
                    [
                        categories[st.character_mission_category_level_master_id].level
                        for st in available
                        if st.stage_order <= claimed
                        and not any(
                            other.stage_order > claimed
                            and other.character_mission_category_level_master_id
                            == st.character_mission_category_level_master_id
                            for other in stages
                        )
                    ]
                    + [row["completedLevel"]]
                )
                await s.update(
                    "CharacterMission",
                    row,
                    rewardReceivedStageOrder=claimed,
                    currentStageMasterId=current.id_,
                    completedLevel=completed,
                )
            rank = rank_before
            balance = points_before + points
            while True:
                level = master("character_star_rank_master", rank, "rank")
                if (
                    not level
                    or level.next_rank_point <= 0
                    or balance < level.next_rank_point
                ):
                    break
                if not master("character_star_rank_master", rank + 1, "rank"):
                    break
                balance -= level.next_rank_point
                rank += 1
            await s.update("CharacterBase", base, starRank=rank, totalStarPoint=balance)
            rewards = []
            for r in cache.star_rank_reward_master:
                if (
                    r.character_base_master_id == mCharacterBaseId
                    and rank_before < r.rank <= rank
                ):
                    group = master(
                        "character_star_rank_reward_group_master",
                        r.character_star_rank_reward_group_master_id,
                    )
                    rewards.extend(
                        (int(t.thing_type), t.thing_id, t.thing_quantity)
                        for t in group.rewards or []
                    )
            received = await s.grant(rewards)
        return respond(
            StarPointResult(
                rank_before=rank_before,
                rank_after=rank,
                star_point_before=points_before,
                star_point_after=balance,
                star_point_acquired=points,
                received_reward=received,
            ),
            present=s.present(),
        )
    except Rejected:
        return respond(StarPointResult())


@router.post("/api/Shops/ExchangeMusic/{mMusicId}")
async def buy_music(request: Request, mMusicId: int):
    from models import ReceivedThing
    from models.enums import ThingTypes

    try:
        async with transaction(request) as s:
            m = master("music_master", mMusicId)
            row = await s.one("Music", musicMasterId=mMusicId)
            if (
                not m
                or m.invisible
                or int(m.unlock_condition_type) not in (10, 11)
                or (row and row["isPossession"])
            ):
                raise Rejected()
            # Story-gated songs require the linked story's episodes to have been read.
            if int(m.unlock_condition_type) == 11:
                episodes = [
                    e
                    for e in cache.episode_master
                    if e.story_master_id == m.story_master_id
                ]
                read = {e["episodeMasterId"] for e in await s.rows("Episode")}
                if not episodes or any(e.id_ not in read for e in episodes):
                    raise Rejected()
            await s.pay({130001: 10})
            if row:
                await s.update("Music", row, isPossession=True)
            else:
                await s.insert(
                    "Music",
                    musicMasterId=mMusicId,
                    isPossession=True,
                    stellaReleased=False,
                    olivierReleaseStatus=0,
                    vocalVersion=0,
                )
        return respond(
            ReceivedThing(type=ThingTypes.Music, id_=mMusicId, quantity=1),
            present=s.present(),
        )
    except Rejected:
        return respond(ReceivedThing())


@router.post("/api/Shops/ExchangeMusicScore/{mLiveId}")
async def buy_chart(request: Request, mLiveId: int):
    from helpers.music_unlock import load_progress

    try:
        async with transaction(request) as s:
            chart = master("live_master", mLiveId)
            if not chart or int(chart.difficulty) != 5:
                raise Rejected()
            from starter_music import grant_default_music
            await grant_default_music(s.conn, s.uid)
            row = await s.one("Music", musicMasterId=chart.music_master_id)
            if not row or not row["isPossession"] or row["olivierReleaseStatus"] == 3:
                raise Rejected()
            progress = await load_progress(s.conn, s.uid)
            if (
                row["olivierReleaseStatus"] != 2
                and chart.level > progress.max_cleared_olivier_level
            ):
                raise Rejected()
            await s.pay({130001: 1})
            await s.update("Music", row, olivierReleaseStatus=3)
            achievement = await s.one("LiveAchievement")
            if achievement:
                await s.update(
                    "LiveAchievement",
                    achievement,
                    olivierReleasedCount=achievement["olivierReleasedCount"] + 1,
                )
        return respond(BooleanResult(is_success=True), present=s.present())
    except Rejected:
        return respond(BooleanResult())


def actor_item_experience(costs, bonus):
    # Official one/two-item captures round each item before multiplying quantity.
    return sum(n * math.floor(experience_item(i).acquirable_experience * (1 + bonus / 100)) for i, n in costs.items())


def actor_experience(level, current, gained, cap, rarity):
    # The master curve is for rarity 4. Rarity 3's 0.8 coefficient is supported
    # by the official 1->2 capture: floor(10*4.6855)-30*0.8 = 22 remaining.
    # Follow-up official captures also verify rarities 1/2/4 at early levels.
    factor = {1: 0.3, 2: 0.5, 3: 0.8, 4: 1.0}[int(rarity)]
    levels = {x.level: x.experience_to_level_up for x in cache.character_level_master}
    experience = current + gained
    while level < cap:
        need = math.floor(levels[level] * factor)
        if need <= 0 or experience < need:
            break
        experience -= need
        level += 1
    return level, experience


@router.post("/api/Characters/{characterId}/AddExperience")
async def actor_level(request: Request, characterId: int):
    from helpers.msgpack import read_request_list

    try:
        payload = await read_request_list(request, UseExperienceItemsPayload)
        costs = Counter()
        raw = 0
        bonus_gain = 0
        for entry in payload or []:
            item = experience_item(entry.item_master_id)
            if not item or entry.quantity < 0:
                raise Rejected()
            costs[entry.item_master_id] += entry.quantity
            raw += item.acquirable_experience * entry.quantity
            bonus_gain += item.acquirable_experience_bonus * entry.quantity
        if raw <= 0:
            raise Rejected()
        async with transaction(request) as s:
            row = await s.one("Character", id=characterId)
            user = await s.one("User")
            bonus = await s.one("UserBonus")
            if not row or not user or not bonus:
                raise Rejected()
            cm = character_master(row["characterMasterId"])
            from helpers.character_level import released_max_level

            cap = min(user["playerRank"], released_max_level())
            if row["level"] >= cap:
                raise Rejected()
            gained = actor_item_experience(costs, bonus["experienceBonus"])
            level, exp = actor_experience(
                row["level"], row["currentExperience"], gained, cap, cm.rarity
            )
            delta = level - row["level"]
            await s.pay(costs)
            await s.update("Character", row, level=level, currentExperience=exp)
            await s.update(
                "UserBonus",
                bonus,
                experienceBonus=f32(bonus["experienceBonus"] + bonus_gain),
            )
            await level_missions(s, cm, delta, level)
        return respond(BooleanResult(is_success=True), present=s.present())
    except Rejected:
        return respond(BooleanResult())


def install(app):
    from helpers.user_data import _camelmap
    _camelmap("AuditionClear").pop("userId", None)
    # FastAPI 0.135+ stores included routers lazily; prepend the override router
    # rather than attempting to remove nested upstream APIRoute objects.
    count = len(app.router.routes)
    app.include_router(router)
    added = app.router.routes[count:]
    app.router.routes[:] = added + app.router.routes[:count]

    import live_modes
    live_modes.install(app)
    import photo_preservation
    photo_preservation.install(app)
    import customization
    customization.install(app)
    import progression
    progression.install(app)
