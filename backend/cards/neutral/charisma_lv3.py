"""Charisma (Level 3) — Neutral Asset (Permanent).
你获得2个额外的盟友槽位。

简化说明：
- 通过 GameState.slot_managers 的 bonus_slots 授予（engine 已将 slot_managers
  暴露到 state 上）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, SlotType, TimingPriority


class Charisma(CardImplementation):
    card_id = "charisma_lv3"
    slot_type = SlotType.ALLY
    bonus = 2

    @on_event(GameEvent.CARD_ENTERS_PLAY, priority=TimingPriority.AFTER)
    def enter_play(self, ctx):
        if ctx.target != self.instance_id:
            return
        mgr = getattr(ctx.game_state, "slot_managers", {}).get(ctx.investigator_id)
        if mgr is not None:
            mgr.add_bonus(self.slot_type, self.bonus)

    @on_event(GameEvent.CARD_LEAVES_PLAY, priority=TimingPriority.AFTER)
    def leaves_play(self, ctx):
        if ctx.target != self.instance_id:
            return
        mgr = getattr(ctx.game_state, "slot_managers", {}).get(ctx.investigator_id)
        if mgr is not None:
            mgr.remove_bonus(self.slot_type, self.bonus)
