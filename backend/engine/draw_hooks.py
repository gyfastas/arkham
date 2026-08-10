"""Hook for CARD_DRAWN that activates the drawn card's implementation.

Player weaknesses (and other cards with "when drawn" effects) need their
CardImplementation registered on the event bus *before* CARD_DRAWN is
emitted, otherwise revelation handlers never fire in real games.

The implementation is activated under a temporary instance_id. After the
event resolves, implementations whose card became persistent (entered the
threat area or play area, e.g. The Necronomicon) stay registered; others
(cards that remain in hand or go to discard) are deactivated — they will be
re-activated through the normal play flow.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from backend.engine.event_bus import EventContext
from backend.models.enums import GameEvent

if TYPE_CHECKING:
    from backend.cards.registry import CardRegistry
    from backend.engine.event_bus import EventBus
    from backend.models.state import GameState, InvestigatorState


def emit_card_drawn(
    game_state: "GameState",
    bus: "EventBus",
    card_registry: "CardRegistry | None",
    inv: "InvestigatorState",
    card_id: str,
    chaos_bag=None,
) -> None:
    """Emit CARD_DRAWN with the drawn card's implementation activated."""
    temp_instance_id: str | None = None
    if card_registry and card_registry.get_implementation(card_id):
        temp_instance_id = game_state.next_instance_id()
        card_registry.activate_card(card_id, temp_instance_id, bus, chaos_bag=chaos_bag)

    ctx = EventContext(
        game_state=game_state,
        event=GameEvent.CARD_DRAWN,
        investigator_id=inv.investigator_id,
        extra={"card_id": card_id},
    )
    bus.emit(ctx)

    if temp_instance_id is None:
        return

    # Keep the registration only if the card became persistent in play.
    persistent_ids = list(inv.threat_area) + list(inv.play_area)
    persistent = any(
        (ci := game_state.get_card_instance(iid)) is not None and ci.card_id == card_id
        for iid in persistent_ids
    )
    if not persistent and card_id in inv.hand:
        # Cards with ongoing "while in hand" effects stay registered.
        impl_class = card_registry.get_implementation(card_id)
        persistent = bool(getattr(impl_class, "persistent_in_hand", False))
    if not persistent:
        card_registry.deactivate_card(temp_instance_id, bus)
