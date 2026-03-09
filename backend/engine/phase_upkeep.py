"""Upkeep Phase: ready, draw, resource, hand size."""

from __future__ import annotations

from typing import TYPE_CHECKING

from backend.models.enums import GameEvent, Phase

if TYPE_CHECKING:
    from backend.engine.event_bus import EventBus, EventContext
    from backend.models.state import GameState

HAND_SIZE_LIMIT = 8


class UpkeepPhase:
    def __init__(self, game_state: GameState, event_bus: EventBus) -> None:
        self.game_state = game_state
        self.bus = event_bus

    def resolve(self, discard_callback=None) -> None:
        """Execute the Upkeep phase (4.1-4.6).

        discard_callback: function(investigator_id, hand, excess) -> list of card_ids to discard.
                         If None, auto-discards from end of hand.
        """
        self.game_state.scenario.current_phase = Phase.UPKEEP

        # 4.1: Phase begins
        self._emit(GameEvent.UPKEEP_PHASE_BEGINS)

        # 4.2: Reset actions (handled at start of investigation phase, skip here)

        # 4.3: Ready all exhausted cards
        self._ready_all()

        # 4.4: Each investigator draws 1 card and gains 1 resource
        self._draw_and_resource()

        # 4.5: Hand size check
        self._check_hand_size(discard_callback)

        # 4.6: Phase ends
        self._emit(GameEvent.UPKEEP_PHASE_ENDS)

    def _ready_all(self) -> None:
        for card in self.game_state.cards_in_play.values():
            if card.exhausted:
                card.exhausted = False
                self._emit(
                    GameEvent.CARD_READIED,
                    target=card.instance_id,
                )

    def _draw_and_resource(self) -> None:
        for inv_id in self.game_state.player_order:
            inv = self.game_state.get_investigator(inv_id)
            if inv is None:
                continue

            # Draw 1 card
            if inv.deck:
                card_id = inv.deck.pop(0)
                inv.hand.append(card_id)
                self._emit(
                    GameEvent.CARD_DRAWN,
                    investigator_id=inv_id,
                    extra={"card_id": card_id},
                )

            # Gain 1 resource
            inv.resources += 1
            self._emit(
                GameEvent.RESOURCES_GAINED,
                investigator_id=inv_id,
                amount=1,
            )

    def _check_hand_size(self, discard_callback) -> None:
        for inv_id in self.game_state.player_order:
            inv = self.game_state.get_investigator(inv_id)
            if inv is None:
                continue

            excess = len(inv.hand) - HAND_SIZE_LIMIT
            if excess <= 0:
                continue

            if discard_callback:
                to_discard = discard_callback(inv_id, inv.hand, excess)
            else:
                # Auto-discard from end of hand
                to_discard = inv.hand[-excess:]

            for card_id in to_discard:
                if card_id in inv.hand:
                    inv.hand.remove(card_id)
                    inv.discard.append(card_id)

    def _emit(self, event: GameEvent, **kwargs) -> None:
        from backend.engine.event_bus import EventContext
        ctx = EventContext(
            game_state=self.game_state,
            event=event,
            **kwargs,
        )
        self.bus.emit(ctx)
