"""Tests for Deep Knowledge (Level 0). (07023)

额外费用：袋中加2个[诅咒]；同地点调查员合计抽3张牌。
"""

import pytest

from backend.cards.seeker.deep_knowledge_lv0 import DeepKnowledge
from backend.engine.event_bus import EventBus, EventContext
from backend.models.chaos import ChaosBag
from backend.models.enums import ChaosTokenType, GameEvent
from backend.models.state import (
    GameState, InvestigatorState, LocationState, ScenarioState,
)
from backend.tests.conftest import (
    make_event_data, make_investigator_data, make_location_data,
)


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()

    inv_data = make_investigator_data()
    state.card_database[inv_data.id] = inv_data
    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1",
    )
    inv.deck = ["d1", "d2", "d3", "d4"]
    state.investigators["inv1"] = inv

    loc_data = make_location_data(id="loc1")
    state.card_database[loc_data.id] = loc_data
    state.locations["loc1"] = LocationState(
        location_id="loc1", card_data=loc_data)

    state.card_database["deep_knowledge_lv0"] = make_event_data(
        id="deep_knowledge_lv0", name="Deep Knowledge")

    impl = DeepKnowledge("inst_dk")
    impl.register(bus, "inst_dk")
    bag = ChaosBag(tokens=[ChaosTokenType.ZERO])
    impl.bind_chaos_bag(bag)
    return state, bus, inv, impl, bag


def _play(state, bus, **extra):
    ctx = EventContext(
        game_state=state, event=GameEvent.CARD_PLAYED,
        investigator_id="inv1", extra={"card_id": "deep_knowledge_lv0", **extra},
    )
    bus.emit(ctx)
    return ctx


class TestDeepKnowledge:
    def test_adds_curses_and_draws_3(self, setup):
        state, bus, inv, impl, bag = setup
        ctx = _play(state, bus)
        assert bag.tokens.count(ChaosTokenType.CURSE) == 2
        assert inv.hand == ["d1", "d2", "d3"]
        assert ctx.extra["deep_knowledge_drawn"] == 3

    def test_distribution_to_other_investigator(self, setup):
        """指定分配：同地点另一名调查员抽2张，你抽1张。"""
        state, bus, inv, impl, bag = setup
        other_data = make_investigator_data(id="inv2", name="Other")
        state.card_database[other_data.id] = other_data
        other = InvestigatorState(
            investigator_id="inv2", card_data=other_data, location_id="loc1",
        )
        other.deck = ["x1", "x2"]
        state.investigators["inv2"] = other

        ctx = _play(state, bus, distribution={"inv2": 2, "inv1": 1})
        assert other.hand == ["x1", "x2"]
        assert inv.hand == ["d1"]
        assert ctx.extra["deep_knowledge_drawn"] == 3
