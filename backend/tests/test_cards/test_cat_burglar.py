"""Tests for Cat Burglar (Level 1)."""

import pytest
from backend.cards.rogue.cat_burglar_lv1 import CatBurglar
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent, Skill
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, LocationState, ScenarioState,
)
from backend.tests.conftest import (
    make_enemy_data, make_investigator_data, make_location_data,
)


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()

    inv_data = make_investigator_data(agility=3)
    state.card_database[inv_data.id] = inv_data

    loc1_data = make_location_data(id="loc1", connections=["loc2"])
    loc2_data = make_location_data(id="loc2", connections=["loc1"])
    state.card_database["loc1"] = loc1_data
    state.card_database["loc2"] = loc2_data
    state.locations["loc1"] = LocationState(
        location_id="loc1", card_data=loc1_data, revealed=True,
    )
    state.locations["loc2"] = LocationState(
        location_id="loc2", card_data=loc2_data, revealed=True,
    )

    enemy_data = make_enemy_data(id="ghoul")
    state.card_database["ghoul"] = enemy_data
    enemy = CardInstance(
        instance_id="ghoul_1", card_id="ghoul",
        owner_id="scenario", controller_id="scenario",
    )
    state.cards_in_play["ghoul_1"] = enemy

    inv = InvestigatorState(
        investigator_id="inv1",
        card_data=inv_data,
        location_id="loc1",
    )
    inv.threat_area.append("ghoul_1")
    state.investigators["inv1"] = inv

    impl = CatBurglar("catburg_inst")
    impl.register(bus, "catburg_inst")

    ci = CardInstance(instance_id="catburg_inst", card_id="cat_burglar_lv1", owner_id="inv1", controller_id="inv1")
    state.cards_in_play["catburg_inst"] = ci
    inv.play_area.append("catburg_inst")

    return state, bus, inv, impl, ci


class TestCatBurglar:
    def test_agility_bonus(self, setup):
        """Cat Burglar provides +1 agility during skill value determination."""
        state, bus, inv, impl, ci = setup

        ctx = EventContext(
            game_state=state,
            event=GameEvent.SKILL_VALUE_DETERMINED,
            investigator_id="inv1",
            skill_type=Skill.AGILITY,
            amount=3,
        )
        bus.emit(ctx)

        assert ctx.amount == 4

    def test_no_bonus_for_other_skills(self, setup):
        """Cat Burglar does not boost non-agility skills."""
        state, bus, inv, impl, ci = setup

        ctx = EventContext(
            game_state=state,
            event=GameEvent.SKILL_VALUE_DETERMINED,
            investigator_id="inv1",
            skill_type=Skill.COMBAT,
            amount=3,
        )
        bus.emit(ctx)

        assert ctx.amount == 3

    def test_activate_disengages_and_moves(self, setup):
        """Exhaust: disengage from each engaged enemy and move to a connecting location."""
        state, bus, inv, impl, ci = setup

        assert impl.activate(state, "inv1") is True
        assert ci.exhausted is True
        assert inv.threat_area == []
        assert "ghoul_1" in state.locations["loc1"].enemies
        assert inv.location_id == "loc2"

    def test_activate_fails_when_exhausted(self, setup):
        state, bus, inv, impl, ci = setup
        ci.exhausted = True
        assert impl.activate(state, "inv1") is False
        assert inv.location_id == "loc1"
