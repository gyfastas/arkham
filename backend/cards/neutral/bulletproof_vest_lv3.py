"""Bulletproof Vest (Level 3) — Neutral Asset, Body slot.
你获得+4生命值。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class BulletproofVest(CardImplementation):
    card_id = "bulletproof_vest_lv3"
    health_bonus = 4

    @on_event(GameEvent.CARD_ENTERS_PLAY, priority=TimingPriority.AFTER)
    def enter_play(self, ctx):
        if ctx.target != self.instance_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is not None:
            inv.health_bonus += self.health_bonus

    @on_event(GameEvent.CARD_LEAVES_PLAY, priority=TimingPriority.AFTER)
    def leaves_play(self, ctx):
        if ctx.target != self.instance_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is not None:
            inv.health_bonus = max(0, inv.health_bonus - self.health_bonus)
