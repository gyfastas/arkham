"""Event bus for game event dispatch and card ability registration."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable

from backend.models.enums import Action, GameEvent, Skill, TimingPriority

if TYPE_CHECKING:
    from backend.models.state import GameState


@dataclass
class EventContext:
    """Context passed to event handlers."""
    game_state: GameState
    event: GameEvent
    source: str | None = None          # card instance_id that triggered this
    target: str | None = None          # target card instance_id
    investigator_id: str | None = None
    skill_type: Skill | None = None
    difficulty: int | None = None
    amount: int = 0                    # damage/horror amount, resources, etc.
    action: Action | None = None
    enemy_id: str | None = None
    location_id: str | None = None
    chaos_token: Any = None
    success: bool | None = None
    modified_skill: int | None = None
    committed_cards: list[str] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)
    cancelled: bool = False
    _modifications: list[tuple[str, int]] = field(default_factory=list, repr=False)

    def modify_amount(self, delta: int, reason: str = "") -> None:
        self._modifications.append((reason, delta))
        self.amount += delta

    def cancel(self) -> None:
        self.cancelled = True


@dataclass
class HandlerEntry:
    event: GameEvent
    handler: Callable[[EventContext], Any]
    priority: TimingPriority
    condition: Callable[[EventContext], bool] | None = None
    card_instance_id: str | None = None

    def matches(self, ctx: EventContext) -> bool:
        if self.condition is None:
            return True
        return self.condition(ctx)


class EventBus:
    def __init__(self) -> None:
        self._handlers: dict[GameEvent, list[HandlerEntry]] = defaultdict(list)
        self._sequence_stack: list[EventContext] = []

    def register(
        self,
        event: GameEvent,
        handler: Callable[[EventContext], Any],
        priority: TimingPriority = TimingPriority.AFTER,
        condition: Callable[[EventContext], bool] | None = None,
        card_instance_id: str | None = None,
    ) -> HandlerEntry:
        entry = HandlerEntry(
            event=event,
            handler=handler,
            priority=priority,
            condition=condition,
            card_instance_id=card_instance_id,
        )
        handlers = self._handlers[event]
        handlers.append(entry)
        # Keep sorted by priority
        handlers.sort(key=lambda h: h.priority.value)
        return entry

    def unregister(self, entry: HandlerEntry) -> None:
        handlers = self._handlers.get(entry.event, [])
        if entry in handlers:
            handlers.remove(entry)

    def unregister_card(self, card_instance_id: str) -> None:
        for event, handlers in self._handlers.items():
            self._handlers[event] = [
                h for h in handlers if h.card_instance_id != card_instance_id
            ]

    def emit(self, ctx: EventContext) -> EventContext:
        self._sequence_stack.append(ctx)
        try:
            handlers = list(self._handlers.get(ctx.event, []))
            for entry in handlers:
                if ctx.cancelled:
                    break
                if entry.matches(ctx):
                    entry.handler(ctx)
            return ctx
        finally:
            self._sequence_stack.pop()

    @property
    def current_context(self) -> EventContext | None:
        return self._sequence_stack[-1] if self._sequence_stack else None

    def clear(self) -> None:
        self._handlers.clear()
        self._sequence_stack.clear()
