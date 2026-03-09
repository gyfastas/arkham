"""Tests for EventBus."""

import pytest
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent, TimingPriority
from backend.models.state import GameState, ScenarioState


@pytest.fixture
def bus():
    return EventBus()


@pytest.fixture
def state():
    return GameState(scenario=ScenarioState(scenario_id="test"))


class TestEventBus:
    def test_register_and_emit(self, bus, state):
        results = []

        def handler(ctx):
            results.append("fired")

        bus.register(GameEvent.ROUND_BEGINS, handler)
        ctx = EventContext(game_state=state, event=GameEvent.ROUND_BEGINS)
        bus.emit(ctx)
        assert results == ["fired"]

    def test_priority_ordering(self, bus, state):
        order = []

        def when_handler(ctx):
            order.append("when")

        def forced_handler(ctx):
            order.append("forced")

        def after_handler(ctx):
            order.append("after")

        def reaction_handler(ctx):
            order.append("reaction")

        bus.register(GameEvent.ROUND_BEGINS, reaction_handler, TimingPriority.REACTION)
        bus.register(GameEvent.ROUND_BEGINS, when_handler, TimingPriority.WHEN)
        bus.register(GameEvent.ROUND_BEGINS, after_handler, TimingPriority.AFTER)
        bus.register(GameEvent.ROUND_BEGINS, forced_handler, TimingPriority.FORCED)

        ctx = EventContext(game_state=state, event=GameEvent.ROUND_BEGINS)
        bus.emit(ctx)
        assert order == ["when", "forced", "after", "reaction"]

    def test_condition_filtering(self, bus, state):
        results = []

        def handler(ctx):
            results.append(ctx.investigator_id)

        bus.register(
            GameEvent.CARD_DRAWN,
            handler,
            condition=lambda ctx: ctx.investigator_id == "alice",
        )

        ctx_alice = EventContext(game_state=state, event=GameEvent.CARD_DRAWN, investigator_id="alice")
        ctx_bob = EventContext(game_state=state, event=GameEvent.CARD_DRAWN, investigator_id="bob")

        bus.emit(ctx_alice)
        bus.emit(ctx_bob)
        assert results == ["alice"]

    def test_cancel_stops_later_handlers(self, bus, state):
        order = []

        def cancel_handler(ctx):
            order.append("cancel")
            ctx.cancel()

        def later_handler(ctx):
            order.append("should_not_fire")

        bus.register(GameEvent.ROUND_BEGINS, cancel_handler, TimingPriority.WHEN)
        bus.register(GameEvent.ROUND_BEGINS, later_handler, TimingPriority.AFTER)

        ctx = EventContext(game_state=state, event=GameEvent.ROUND_BEGINS)
        bus.emit(ctx)
        assert order == ["cancel"]
        assert ctx.cancelled

    def test_unregister_card(self, bus, state):
        results = []

        def handler(ctx):
            results.append("fired")

        bus.register(GameEvent.ROUND_BEGINS, handler, card_instance_id="card_1")
        bus.unregister_card("card_1")

        ctx = EventContext(game_state=state, event=GameEvent.ROUND_BEGINS)
        bus.emit(ctx)
        assert results == []

    def test_nested_emit(self, bus, state):
        order = []

        def outer_handler(ctx):
            order.append("outer_start")
            inner_ctx = EventContext(game_state=state, event=GameEvent.CARD_DRAWN)
            bus.emit(inner_ctx)
            order.append("outer_end")

        def inner_handler(ctx):
            order.append("inner")

        bus.register(GameEvent.ROUND_BEGINS, outer_handler)
        bus.register(GameEvent.CARD_DRAWN, inner_handler)

        ctx = EventContext(game_state=state, event=GameEvent.ROUND_BEGINS)
        bus.emit(ctx)
        assert order == ["outer_start", "inner", "outer_end"]

    def test_modify_amount(self, bus, state):
        def modifier(ctx):
            ctx.modify_amount(2, "bonus")

        bus.register(GameEvent.DAMAGE_DEALT, modifier)

        ctx = EventContext(game_state=state, event=GameEvent.DAMAGE_DEALT, amount=1)
        bus.emit(ctx)
        assert ctx.amount == 3

    def test_clear(self, bus, state):
        results = []
        bus.register(GameEvent.ROUND_BEGINS, lambda ctx: results.append(1))
        bus.clear()

        ctx = EventContext(game_state=state, event=GameEvent.ROUND_BEGINS)
        bus.emit(ctx)
        assert results == []
