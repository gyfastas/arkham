"""Lockpicks (Level 1) — Rogue Asset, Hand slot.
使用(3补给)。消耗撬锁工具：调查。你获得+3智力。如果这次检定失败，弃置撬锁工具。

简化说明：
- activate() 花费1补给并武装；随后由会话层发起调查行动。
"""

from backend.cards.base import CardImplementation, on_event
from backend.engine.slots import vacate_asset_slots
from backend.models.enums import GameEvent, Skill, TimingPriority


class Lockpicks(CardImplementation):
    card_id = "lockpicks_lv1"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._armed = False

    def activate(self, game_state, investigator_id: str) -> bool:
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return False
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None or inst.uses.get("supply", 0) <= 0:
            return False
        inst.uses["supply"] -= 1
        inst.exhausted = True
        self._armed = True
        return True

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def intellect_bonus(self, ctx):
        if not self._armed or ctx.skill_type != Skill.INTELLECT:
            return
        ctx.modify_amount(3, "lockpicks_bonus")

    @on_event(GameEvent.SKILL_TEST_FAILED, priority=TimingPriority.AFTER)
    def discard_on_fail(self, ctx):
        """检定失败：弃置撬锁工具。"""
        if not self._armed:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        vacate_asset_slots(ctx.game_state, self.instance_id)
        inv.play_area.remove(self.instance_id)
        ctx.game_state.cards_in_play.pop(self.instance_id, None)
        inv.discard.append("lockpicks_lv1")
        ctx.extra["lockpicks_discarded"] = True

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        self._armed = False
