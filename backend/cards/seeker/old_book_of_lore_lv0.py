"""Old Book of Lore (Level 0) — Seeker Asset, Hand slot.
消耗：查看目标调查员牌库顶部3张牌，选择1张加入手牌，其余洗回牌库。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class OldBookOfLore(CardImplementation):
    card_id = "old_book_of_lore_lv0"

    def activate(self, ctx, target_id: str | None = None):
        """Exhaust: look at top 3 cards of target investigator's deck, draw 1.

        For now, simplified: draw the top card of the target's deck.
        Full implementation would present a choice of 3 cards.
        """
        inv_id = target_id or ctx.investigator_id
        inv = ctx.game_state.get_investigator(inv_id)
        if inv is None:
            return
        if not inv.deck:
            return
        # Simplified: draw top card (full version would show top 3, pick 1)
        card = inv.deck.pop(0)
        inv.hand.append(card)

    @on_event(
        GameEvent.CARD_EXHAUSTED,
        priority=TimingPriority.AFTER,
    )
    def on_exhaust(self, ctx):
        """Skeleton handler for exhaust trigger — actual activation via activate()."""
        if ctx.target != self.instance_id:
            return
        # The real activation is handled by the activate() method
        # called from the action system. This handler exists for
        # event-bus tracking purposes.
        pass
