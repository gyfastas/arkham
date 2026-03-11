"""Captures game engine events as a chronological log for client animation.

Hooks into the EventBus and records events that the frontend should animate
(chaos token reveal, damage, card play, enemy defeat, etc.).
"""

from __future__ import annotations

from typing import Any

from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent, TimingPriority


# Events worth capturing for client-side animation
ANIMATABLE_EVENTS = [
    GameEvent.CHAOS_TOKEN_REVEALED,
    GameEvent.SKILL_TEST_SUCCESSFUL,
    GameEvent.SKILL_TEST_FAILED,
    GameEvent.DAMAGE_DEALT,
    GameEvent.HORROR_DEALT,
    GameEvent.CARD_PLAYED,
    GameEvent.CARD_DRAWN,
    GameEvent.CARD_ENTERS_PLAY,
    GameEvent.CARD_LEAVES_PLAY,
    GameEvent.ENEMY_DEFEATED,
    GameEvent.ENEMY_EVADED,
    GameEvent.ENEMY_ENGAGED,
    GameEvent.ENEMY_ATTACKS,
    GameEvent.CLUE_DISCOVERED,
    GameEvent.RESOURCES_GAINED,
    GameEvent.RESOURCES_SPENT,
    GameEvent.MOVE_ACTION_INITIATED,
    GameEvent.ACTION_PERFORMED,
    GameEvent.INVESTIGATOR_DEFEATED,
    GameEvent.AGENDA_ADVANCED,
]


def _serialize_event(ctx: EventContext) -> dict[str, Any]:
    """Convert an EventContext into a JSON-serializable dict."""
    data: dict[str, Any] = {
        "event": ctx.event.name,
    }
    if ctx.investigator_id:
        data["investigator_id"] = ctx.investigator_id
    if ctx.amount:
        data["amount"] = ctx.amount
    if ctx.chaos_token is not None:
        data["chaos_token"] = ctx.chaos_token.value if hasattr(ctx.chaos_token, "value") else str(ctx.chaos_token)
    if ctx.success is not None:
        data["success"] = ctx.success
    if ctx.target:
        data["target"] = ctx.target
    if ctx.source:
        data["source"] = ctx.source
    if ctx.enemy_id:
        data["enemy_id"] = ctx.enemy_id
    if ctx.location_id:
        data["location_id"] = ctx.location_id
    if ctx.skill_type:
        data["skill_type"] = ctx.skill_type.value
    if ctx.difficulty is not None:
        data["difficulty"] = ctx.difficulty
    if ctx.action:
        data["action"] = ctx.action.name
    if ctx.modified_skill is not None:
        data["modified_skill"] = ctx.modified_skill
    if ctx.extra:
        # Include card_id from extra if present
        if "card_id" in ctx.extra:
            data["card_id"] = ctx.extra["card_id"]
    return data


class EventLogger:
    """Captures game events for client animation replay.

    Usage::

        logger = EventLogger(game.event_bus)
        # ... perform game actions ...
        events = logger.flush()  # Returns and clears captured events
    """

    def __init__(self, event_bus: EventBus) -> None:
        self._events: list[dict[str, Any]] = []
        self._entries: list = []
        for event_type in ANIMATABLE_EVENTS:
            entry = event_bus.register(
                event_type,
                self._capture,
                priority=TimingPriority.REACTION,  # Run last, after all game effects
            )
            self._entries.append(entry)

    def _capture(self, ctx: EventContext) -> None:
        self._events.append(_serialize_event(ctx))

    def flush(self) -> list[dict[str, Any]]:
        """Return captured events and clear the buffer."""
        events = list(self._events)
        self._events.clear()
        return events

    def detach(self, event_bus: EventBus) -> None:
        """Unregister all handlers from the event bus."""
        for entry in self._entries:
            event_bus.unregister(entry)
        self._entries.clear()
