"""Mitch Brown (Level 0) — Neutral Asset, Ally slot. Leo Anderson 专属.
你获得2个额外的盟友槽位，且这些槽位只能用于非独特盟友。

简化说明：
- 槽位授予同 charisma_lv3（SlotManager.add_bonus）。
- 引擎 SlotManager 的限制槽位按 trait 判定，无法表达"非独特"限制
  （引擎缺口）；当前按通用盟友槽位授予，独特性限制由会话层负责。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, SlotType, TimingPriority


class MitchBrown(CardImplementation):
    card_id = "mitch_brown_lv0"
    bonus = 2

    @on_event(GameEvent.CARD_ENTERS_PLAY, priority=TimingPriority.AFTER)
    def enter_play(self, ctx):
        if ctx.target != self.instance_id:
            return
        mgr = getattr(ctx.game_state, "slot_managers", {}).get(ctx.investigator_id)
        if mgr is not None:
            mgr.add_bonus(SlotType.ALLY, self.bonus)

    @on_event(GameEvent.CARD_LEAVES_PLAY, priority=TimingPriority.AFTER)
    def leaves_play(self, ctx):
        if ctx.target != self.instance_id:
            return
        mgr = getattr(ctx.game_state, "slot_managers", {}).get(ctx.investigator_id)
        if mgr is not None:
            mgr.remove_bonus(SlotType.ALLY, self.bonus)
