"""Base class for card implementations with event binding decorators."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable

from backend.models.enums import GameEvent, TimingPriority

if TYPE_CHECKING:
    from backend.engine.event_bus import EventBus, EventContext


@dataclass
class EventBinding:
    event: GameEvent
    priority: TimingPriority = TimingPriority.AFTER
    condition: Callable[[EventContext], bool] | None = None


def on_event(
    event: GameEvent,
    priority: TimingPriority = TimingPriority.AFTER,
    when: Callable[[EventContext], bool] | None = None,
) -> Callable:
    """Decorator that marks a method as a handler for a GameEvent."""
    def decorator(method: Callable) -> Callable:
        if not hasattr(method, '_event_bindings'):
            method._event_bindings = []
        method._event_bindings.append(EventBinding(
            event=event,
            priority=priority,
            condition=when,
        ))
        return method
    return decorator


class CardImplementation:
    """Base class for all card effect implementations.

    Subclasses define card_id and use @on_event to register handlers.
    """
    card_id: str = ""

    def __init__(self, instance_id: str = "") -> None:
        self.instance_id = instance_id

    def register(self, bus: EventBus, instance_id: str) -> None:
        """Auto-discover all @on_event methods and register them on the bus."""
        self.instance_id = instance_id
        for attr_name in dir(self):
            if attr_name.startswith('_'):
                continue
            method = getattr(self, attr_name, None)
            if method is None or not callable(method):
                continue
            bindings: list[EventBinding] = getattr(method, '_event_bindings', [])
            for binding in bindings:
                # Wrap condition to include instance check
                original_condition = binding.condition

                def make_condition(cond):
                    def wrapped(ctx):
                        if cond is None:
                            return True
                        return cond(ctx)
                    return wrapped

                bus.register(
                    event=binding.event,
                    handler=method,
                    priority=binding.priority,
                    condition=make_condition(original_condition),
                    card_instance_id=instance_id,
                )

    def unregister(self, bus: EventBus) -> None:
        bus.unregister_card(self.instance_id)
