"""The Necronomicon: John Dee Translation — Neutral Asset (Signature Weakness).
揭示：放入威胁区域，上面放3个恐惧。有恐惧时不能离场。
自由行动：将1个恐惧从死灵之书移到黛西身上。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class TheNecronomicon(CardImplementation):
    card_id = "the_necronomicon"

    @on_event(
        GameEvent.CARD_DRAWN,
        priority=TimingPriority.WHEN,
    )
    def revelation(self, ctx):
        """Revelation: When drawn, put into threat area with 3 horror tokens.

        The Necronomicon enters play in the threat area (not hand),
        with 3 horror tokens on it.
        """
        if ctx.extra.get("card_id") != "the_necronomicon":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        # Remove from hand if it was added there
        if "the_necronomicon" in inv.hand:
            inv.hand.remove("the_necronomicon")

        # Create card instance in play (threat area)
        from backend.models.state import CardInstance
        inst_id = ctx.game_state.next_instance_id()
        ci = CardInstance(
            instance_id=inst_id,
            card_id="the_necronomicon",
            owner_id=ctx.investigator_id,
            controller_id=ctx.investigator_id,
        )
        ci.uses = {"horror": 3}
        ctx.game_state.cards_in_play[inst_id] = ci
        inv.threat_area.append(inst_id)

    @on_event(
        GameEvent.ACTION_PERFORMED,
        priority=TimingPriority.AFTER,
    )
    def move_horror(self, ctx):
        """Free action: Move 1 horror from Necronomicon to the investigator.

        In a full implementation, this would be an Activate action on the card.
        When horror reaches 0, the Necronomicon can be discarded.
        """
        # This is a skeleton — actual activation requires UI interaction.
        # The action would be triggered by a specific "ACTIVATE" action targeting
        # this card's instance_id.
        pass

    def activate(self, game_state, investigator_id):
        """Activate ability: Move 1 horror to investigator.

        Call this method when the player chooses to activate the Necronomicon.
        """
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return False

        ci = game_state.get_card_instance(self.instance_id)
        if ci is None or ci.uses.get("horror", 0) <= 0:
            return False

        ci.uses["horror"] -= 1
        inv.horror += 1

        # If no horror left, it can now leave play (discard)
        if ci.uses["horror"] <= 0:
            if self.instance_id in inv.threat_area:
                inv.threat_area.remove(self.instance_id)
            inv.discard.append(ci.card_id)
            del game_state.cards_in_play[self.instance_id]

        return True
