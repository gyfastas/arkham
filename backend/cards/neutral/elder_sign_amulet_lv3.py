"""Elder Sign Amulet (Level 3) — Neutral Asset, Accessory slot.
你获得+4理智。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class ElderSignAmulet(CardImplementation):
    card_id = "elder_sign_amulet_lv3"
    sanity_bonus = 4

    @on_event(GameEvent.CARD_ENTERS_PLAY, priority=TimingPriority.AFTER)
    def enter_play(self, ctx):
        if ctx.target != self.instance_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is not None:
            inv.sanity_bonus += self.sanity_bonus

    @on_event(GameEvent.CARD_LEAVES_PLAY, priority=TimingPriority.AFTER)
    def leaves_play(self, ctx):
        if ctx.target != self.instance_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is not None:
            inv.sanity_bonus = max(0, inv.sanity_bonus - self.sanity_bonus)
