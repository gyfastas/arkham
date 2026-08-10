"""Pickpocketing (Level 0) — Rogue Asset.
反应 - 在你躲避一个敌人后，消耗扒窃：抽1张牌。
"""
from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class Pickpocketing(CardImplementation):
    card_id = "pickpocketing_lv0"

    @on_event(GameEvent.ENEMY_EVADED, priority=TimingPriority.REACTION)
    def draw_card(self, ctx):
        """After you evade an enemy, exhaust Pickpocketing to draw 1 card."""
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is None or inst.exhausted:
            return
        if not inv.deck:
            return
        inst.exhausted = True
        inv.hand.append(inv.deck.pop(0))
        ctx.extra["pickpocketing_draw"] = True
