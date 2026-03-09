"""Laboratory Assistant (Level 0) — Seeker Asset, Ally slot.
手牌上限+2。进场时抓2张牌。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class LaboratoryAssistant(CardImplementation):
    card_id = "laboratory_assistant_lv0"

    @on_event(
        GameEvent.CARD_ENTERS_PLAY,
        priority=TimingPriority.REACTION,
    )
    def draw_on_enter(self, ctx):
        """When Laboratory Assistant enters play, draw 2 cards."""
        if ctx.target != self.instance_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        for _ in range(2):
            if inv.deck:
                inv.hand.append(inv.deck.pop(0))

    @on_event(
        GameEvent.UPKEEP_PHASE_BEGINS,
        priority=TimingPriority.WHEN,
    )
    def increase_hand_size(self, ctx):
        """Passively increase max hand size by 2 while in play."""
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv and self.instance_id in inv.play_area:
            ctx.modify_amount(2, "laboratory_assistant_hand_size")
