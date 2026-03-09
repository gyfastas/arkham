"""Tests for Holy Rosary (Level 0)."""

import pytest
from backend.cards.mystic.holy_rosary_lv0 import HolyRosary
from backend.engine.event_bus import EventBus
from backend.engine.skill_test import SkillTestEngine
from backend.models.chaos import ChaosBag
from backend.models.enums import ChaosTokenType, Skill
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, ScenarioState,
)
from backend.tests.conftest import make_asset_data, make_investigator_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()
    bag = ChaosBag()
    bag.seed(42)

    inv_data = make_investigator_data(willpower=3)
    state.card_database[inv_data.id] = inv_data

    rosary_data = make_asset_data(
        id="holy_rosary_lv0", name="Holy Rosary",
        traits=["item", "charm"],
    )
    state.card_database["holy_rosary_lv0"] = rosary_data

    inv = InvestigatorState(
        investigator_id="inv1",
        card_data=inv_data,
        location_id="loc1",
        deck=["card_a", "card_b"],
    )
    state.investigators["inv1"] = inv

    impl = HolyRosary("inst_rosary")
    impl.register(bus, "inst_rosary")

    ci = CardInstance(
        instance_id="inst_rosary", card_id="holy_rosary_lv0",
        owner_id="inv1", controller_id="inv1",
    )
    state.cards_in_play["inst_rosary"] = ci
    inv.play_area.append("inst_rosary")

    engine = SkillTestEngine(state, bus, bag)
    return state, bus, bag, engine, inv


class TestHolyRosary:
    def test_card_id(self, setup):
        state, bus, bag, engine, inv = setup
        assert "holy_rosary_lv0" in state.card_database

    def test_willpower_bonus(self, setup):
        """Holy Rosary provides +1 willpower during skill tests."""
        state, bus, bag, engine, inv = setup
        bag.tokens = [ChaosTokenType.ZERO]

        # Base willpower 3 + 1 rosary = 4 vs difficulty 4 -> success
        result = engine.run_test(
            investigator_id="inv1",
            skill_type=Skill.WILLPOWER,
            difficulty=4,
        )
        assert result.success
