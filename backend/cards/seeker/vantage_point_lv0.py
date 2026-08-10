"""Vantage Point (Level 0) — Seeker Event, Fast. (04306)
快速。在一位调查员的回合内，在一个地点入场或被翻开后打出。
该地点-1隐藏值，直到当前调查员的回合结束。你可以将其它任何地点上的
1个线索移动到该地点上。

简化说明：
- 打出时机由会话层校验；目标地点由 ctx.extra["location_id"] 指定，
  缺省为你所在地点；
- 地点的隐藏值是只读属性，-1隐藏值以降低该地点智力检定难度的方式生效
  （INVESTIGATE_ACTION_INITIATED 锁定地点，SKILL_TEST_BEGINS 降难度），
  当前调查员回合结束过期；
- 移动线索为可选项，自动取有利分支：第一个有线索的其它地点移1个线索
  到目标地点（均无则不移）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class VantagePoint(CardImplementation):
    card_id = "vantage_point_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._location_id: str | None = None   # 被减隐藏值的地点
        self._investigating: str | None = None  # 本次调查检定的目标地点

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def resolve(self, ctx):
        if ctx.extra.get("card_id") != self.card_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        target_id = ctx.extra.get("location_id") or (
            inv.location_id if inv is not None else None)
        target = ctx.game_state.get_location(target_id) if target_id else None
        if target is None:
            return
        self._location_id = target.location_id
        ctx.extra["vantage_point_location"] = target.location_id

        # 可选项：将其它地点的1个线索移动到目标地点
        for loc in ctx.game_state.locations.values():
            if loc.location_id == target.location_id or loc.clues < 1:
                continue
            loc.clues -= 1
            target.clues += 1
            ctx.extra["vantage_point_moved_from"] = loc.location_id
            ctx.game_state.log_effect(
                f"🧭 有利位置：【{ctx.game_state.card_name(target.location_id)}】"
                "本回合-1隐藏值，从其它地点移来1个线索")
            break
        else:
            ctx.game_state.log_effect(
                f"🧭 有利位置：【{ctx.game_state.card_name(target.location_id)}】"
                "本回合-1隐藏值")

    @on_event(GameEvent.INVESTIGATE_ACTION_INITIATED, priority=TimingPriority.AFTER)
    def track_investigate(self, ctx):
        self._investigating = ctx.location_id

    @on_event(GameEvent.SKILL_TEST_BEGINS, priority=TimingPriority.WHEN)
    def reduce_shroud(self, ctx):
        """对目标地点的调查检定：难度-1（-1隐藏值）。"""
        if self._location_id is None or ctx.skill_type != Skill.INTELLECT:
            return
        if self._investigating != self._location_id:
            return
        if ctx.difficulty is not None and ctx.difficulty > 0:
            ctx.difficulty = ctx.difficulty - 1
            ctx.extra["vantage_point_reduced"] = True

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear_test(self, ctx):
        self._investigating = None

    @on_event(GameEvent.INVESTIGATOR_TURN_ENDS, priority=TimingPriority.AFTER)
    def expire(self, ctx):
        """"直到当前调查员的回合结束"：任意回合结束即过期。"""
        self._location_id = None
        self._investigating = None
