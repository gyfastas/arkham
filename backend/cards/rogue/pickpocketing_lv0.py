"""Pickpocketing (Level 0) — Rogue Asset.
扒窃。在你成功闪避敌人后，消耗：抽1张卡。
"""
from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class Pickpocketing(CardImplementation):
    card_id = "pickpocketing_lv0"

    @on_event(GameEvent.ENEMY_EVADED, priority=TimingPriority.REACTION)
    def draw_card(self, ctx):
        """After you evade an enemy, exhaust to draw 1 card."""
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv and self.instance_id in inv.play_area and inv.deck:
            inv.hand.append(inv.deck.pop(0))
