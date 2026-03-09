"""Tests for Magnifying Glass (Level 1)."""

import pytest
from backend.cards.seeker.magnifying_glass_lv1 import MagnifyingGlassLv1
from backend.engine.event_bus import EventBus
from backend.engine.skill_test import SkillTestEngine
from backend.models.chaos import ChaosBag
from backend.models.enums import ChaosTokenType, Skill
from backend.models.state import GameState, InvestigatorState, LocationState, ScenarioState, CardInstance
from backend.tests.conftest import make_investigator_data, make_location_data, make_asset_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()
    bag = ChaosBag()
    bag.seed(42)

    inv_data = make_investigator_data(intellect=3)
    state.card_database[inv_data.id] = inv_data

    mag_data = make_asset_data(
        id="magnifying_glass_lv1", name="Magnifying Glass",
        skill_icons={"intellect": 1},
    )
    state.card_database["magnifying_glass_lv1"] = mag_data

    loc_data = make_location_data(shroud=3)
    state.card_database[loc_data.id] = loc_data

    inv = InvestigatorState(
        investigator_id="inv1",
        card_data=inv_data,
        location_id="test_location",
        deck=["card_a", "card_b"],
    )
    state.investigators["inv1"] = inv

    loc = LocationState(location_id="test_location", card_data=loc_data, clues=3)
    state.locations["test_location"] = loc

    impl = MagnifyingGlassLv1("inst_mag1")
    impl.register(bus, "inst_mag1")

    ci = CardInstance(instance_id="inst_mag1", card_id="magnifying_glass_lv1", owner_id="inv1", controller_id="inv1")
    state.cards_in_play["inst_mag1"] = ci
    inv.play_area.append("inst_mag1")

    engine = SkillTestEngine(state, bus, bag)
    return state, bus, bag, engine, inv, loc


class TestMagnifyingGlassLv1:
    def test_intellect_bonus(self, setup):
        """Magnifying Glass Lv1 provides +1 intellect during skill tests."""
        state, bus, bag, engine, inv, loc = setup
        bag.tokens = [ChaosTokenType.ZERO]

        # Base intellect 3 + 1 mag glass bonus = 4 vs difficulty 4 -> success
        result = engine.run_test(
            investigator_id="inv1",
            skill_type=Skill.INTELLECT,
            difficulty=4,
        )
        assert result.success

    def test_card_has_intellect_icon(self, setup):
        """Magnifying Glass Lv1 card data has intellect skill icon."""
        state, bus, bag, engine, inv, loc = setup
        card_data = state.card_database["magnifying_glass_lv1"]
        assert card_data.skill_icons.get("intellect") == 1
