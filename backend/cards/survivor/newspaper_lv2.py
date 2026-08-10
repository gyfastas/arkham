"""Newspaper (Level 2) — Survivor Asset.
只要你没有线索，调查时你获得+2智力。
[reaction] 在你将要发现你所在地点的1个或以上线索时，如果你没有线索：
发现你所在地点的额外1个线索。

简化说明：
- "调查时"通过 INVESTIGATE_ACTION_INITIATED 跟踪（SKILL_TEST_ENDS 清除），
  普通智力检定（如诡计卡）不享受加值（同 scavenging 模式）。
- 反应能力挂 CLUE_DISCOVERED（引擎在线索落袋后发出）：
  "如果你没有线索"按"本次发现前无线索"判定（当前线索数==本次发现数）；
  额外线索受所在地点剩余线索限制。地点无线索时不触发（官方为"将要发现"
  的打断窗口，引擎无此前置通道，从简）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class Newspaper(CardImplementation):
    card_id = "newspaper_lv2"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._investigating: str | None = None

    @on_event(GameEvent.INVESTIGATE_ACTION_INITIATED, priority=TimingPriority.AFTER)
    def track_investigate(self, ctx):
        self._investigating = ctx.investigator_id

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear_tracking(self, ctx):
        self._investigating = None

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def intellect_bonus(self, ctx):
        """没有线索时，调查+2智力。"""
        if ctx.skill_type != Skill.INTELLECT:
            return
        if self._investigating != ctx.investigator_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        if inv.clues != 0:
            return
        ctx.modify_amount(2, "newspaper_no_clue_intellect")

    @on_event(GameEvent.CLUE_DISCOVERED, priority=TimingPriority.REACTION)
    def bonus_clue(self, ctx):
        """无线索时发现线索：额外发现所在地点1个线索。"""
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        if (ctx.amount or 0) < 1:
            return
        # "如果你没有线索"：当前线索全部来自本次发现 → 发现前为0
        if inv.clues != ctx.amount:
            return
        if ctx.location_id and ctx.location_id != inv.location_id:
            return
        loc = ctx.game_state.get_location(inv.location_id)
        if loc is None or loc.clues <= 0:
            return
        loc.clues -= 1
        inv.clues += 1
        ctx.extra["newspaper_bonus_clue"] = True
        ctx.game_state.log_effect("📰 报纸：额外发现1个线索")
