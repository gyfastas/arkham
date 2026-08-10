"""Magnifying Glass (Level 0) — Seeker Asset, Hand slot. Fast.
快速。调查时你获得+1智力。

说明：
- "调查时"通过 INVESTIGATE_ACTION_INITIATED 跟踪（SKILL_TEST_ENDS 清除），
  非调查的智力检定（如诡计卡检定）不享受加值——与 dr_milan/rex_murphy 同模式。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class MagnifyingGlass(CardImplementation):
    card_id = "magnifying_glass_lv0"

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
        """+1 Intellect while investigating."""
        if ctx.skill_type != Skill.INTELLECT:
            return
        if self._investigating != ctx.investigator_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv and self.instance_id in inv.play_area:
            ctx.modify_amount(1, "magnifying_glass_bonus")
