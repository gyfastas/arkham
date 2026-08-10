"""Magnifying Glass (Level 1) — Seeker Asset, Hand slot. Fast.
快速。调查时你获得+1智力。[快速]如果你所在地点没有线索：将放大镜收回手牌。

简化说明：
- "调查时"通过 INVESTIGATE_ACTION_INITIATED 跟踪（SKILL_TEST_ENDS 清除）；
- 收回手牌是可选的[快速]能力，当前无可选窗口，简化为地点线索耗尽时
  自动收回（CLUE_DISCOVERED 后检查）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.engine.slots import vacate_asset_slots
from backend.models.enums import GameEvent, Skill, TimingPriority


class MagnifyingGlassLv1(CardImplementation):
    card_id = "magnifying_glass_lv1"

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
            ctx.modify_amount(1, "magnifying_glass_lv1_bonus")

    @on_event(GameEvent.CLUE_DISCOVERED, priority=TimingPriority.AFTER)
    def check_return_to_hand(self, ctx):
        """地点线索耗尽后自动收回手牌（可选[快速]能力的简化，见 docstring）。"""
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if self.instance_id not in inv.play_area:
            return
        location = ctx.game_state.get_location(inv.location_id)
        if location and location.clues == 0:
            # Return to hand（手牌存 card_id；实例移出场面）
            vacate_asset_slots(ctx.game_state, self.instance_id)
            inv.play_area.remove(self.instance_id)
            ctx.game_state.cards_in_play.pop(self.instance_id, None)
            inv.hand.append("magnifying_glass_lv1")
