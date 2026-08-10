"""Tests for Treasure Hunter (Level 1)."""

import pytest

from backend.cards.rogue.treasure_hunter_lv1 import TreasureHunter
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent, Skill
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, ScenarioState,
)
from backend.tests.conftest import make_investigator_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()
    inv_data = make_investigator_data(intellect=3)
    state.card_database[inv_data.id] = inv_data
    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1")
    inv.resources = 2
    state.investigators["inv1"] = inv
    inst = CardInstance(
        instance_id="th_inst", card_id="treasure_hunter_lv1",
        owner_id="inv1", controller_id="inv1",
    )
    state.cards_in_play["th_inst"] = inst
    inv.play_area.append("th_inst")
    impl = TreasureHunter("th_inst")
    impl.register(bus, "th_inst")
    return state, bus, inv, inst


def _upkeep_end(bus, state):
    ctx = EventContext(game_state=state, event=GameEvent.UPKEEP_PHASE_ENDS)
    bus.emit(ctx)
    return ctx


class TestTreasureHunter:
    def test_intellect_bonus(self, setup):
        state, bus, inv, inst = setup
        ctx = EventContext(
            game_state=state,
            event=GameEvent.SKILL_VALUE_DETERMINED,
            investigator_id="inv1",
            skill_type=Skill.INTELLECT,
            amount=3,
        )
        bus.emit(ctx)
        assert ctx.amount == 4

    def test_no_bonus_other_skill(self, setup):
        state, bus, inv, inst = setup
        ctx = EventContext(
            game_state=state,
            event=GameEvent.SKILL_VALUE_DETERMINED,
            investigator_id="inv1",
            skill_type=Skill.AGILITY,
            amount=3,
        )
        bus.emit(ctx)
        assert ctx.amount == 3

    def test_upkeep_pays_one_resource(self, setup):
        state, bus, inv, inst = setup
        ctx = _upkeep_end(bus, state)
        assert inv.resources == 1
        assert ctx.extra["treasure_hunter_paid"] is True
        assert "th_inst" in inv.play_area

    def test_upkeep_discards_when_broke(self, setup):
        state, bus, inv, inst = setup
        inv.resources = 0
        ctx = _upkeep_end(bus, state)
        assert ctx.extra["treasure_hunter_discarded"] is True
        assert "th_inst" not in inv.play_area
        assert "th_inst" not in state.cards_in_play
        assert "treasure_hunter_lv1" in inv.discard
