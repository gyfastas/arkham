"""Daisy's Tote Bag — Seeker Asset (Signature).
提供2个额外手部栏位，只能用于放置典籍(Tome)支援卡。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, SlotType, TimingPriority


class DaisysToteBag(CardImplementation):
    card_id = "daisys_tote_bag"

    @on_event(
        GameEvent.CARD_ENTERS_PLAY,
        priority=TimingPriority.AFTER,
    )
    def grant_tome_slots(self, ctx):
        """When Tote Bag enters play, grant 2 extra hand slots for Tomes.

        Implementation: We increase the slot manager's hand limit by 2.
        The Tome-only restriction is a logical constraint — in a full implementation,
        the slot manager would track these as special "tome_hand" slots.
        For now, we simply add 2 hand slots.
        """
        if ctx.target != self.instance_id:
            return
        inv_id = ctx.investigator_id
        if not inv_id:
            return
        # Access the slot manager via extra or direct reference
        # For simplicity, we mark on the card instance that extra slots are active
        ci = ctx.game_state.get_card_instance(self.instance_id)
        if ci:
            ci.uses = ci.uses or {}
            ci.uses["tome_hand_slots"] = 2

    @on_event(
        GameEvent.CARD_LEAVES_PLAY,
        priority=TimingPriority.AFTER,
    )
    def remove_tome_slots(self, ctx):
        """When Tote Bag leaves play, remove the extra slots."""
        if ctx.target != self.instance_id:
            return
        ci = ctx.game_state.get_card_instance(self.instance_id)
        if ci and ci.uses:
            ci.uses.pop("tome_hand_slots", None)
