"""Tests for Stunning Blow (Level 0)."""

import pytest
from backend.cards.survivor.stunning_blow_lv0 import StunningBlow
from backend.engine.event_bus import EventBus
from backend.engine.skill_test import SkillTestEngine
from backend.models.chaos import ChaosBag
from backend.models.enums import ChaosTokenType, Skill
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, LocationState, ScenarioState,
)
from backend.tests.conftest import (
    make_enemy_data, make_investigator_data, make_location_data, make_skill_data,
)


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()
    bag = ChaosBag()
    bag.seed(42)

    inv_data = make_investigator_data(combat=5)
    state.card_database[inv_data.id] = inv_data
    state.card_database["stunning_blow_lv0"] = make_skill_data(
        id="stunning_blow_lv0", skill_icons={"combat": 1})
    enemy_data = make_enemy_data(fight=3)
    state.card_database[enemy_data.id] = enemy_data
    loc_data = make_location_data()
    state.card_database[loc_data.id] = loc_data

    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data,
        location_id="test_location", hand=["stunning_blow_lv0"],
    )
    state.investigators["inv1"] = inv
    state.locations["test_location"] = LocationState(
        location_id="test_location", card_data=loc_data)

    state.cards_in_play["enemy_1"] = CardInstance(
        instance_id="enemy_1", card_id="test_enemy",
        owner_id="scenario", controller_id="scenario",
    )
    inv.threat_area.append("enemy_1")

    engine = SkillTestEngine(state, bus, bag)
    impl = StunningBlow("sb_inst")
    impl.register(bus, "sb_inst")
    return state, bus, bag, engine, inv


class TestStunningBlow:
    def test_successful_attack_auto_evades(self, setup):
        """攻击成功：自动躲避交战敌人（横置+脱离+留在地点）。"""
        state, bus, bag, engine, inv = setup
        bag.tokens = [ChaosTokenType.ZERO]
        result = engine.run_test(
            investigator_id="inv1", skill_type=Skill.COMBAT,
            difficulty=3, committed_card_ids=["stunning_blow_lv0"],
        )
        assert result.success
        enemy = state.get_card_instance("enemy_1")
        loc = state.get_location("test_location")
        assert enemy.exhausted
        assert "enemy_1" not in inv.threat_area
        assert "enemy_1" in loc.enemies

    def test_failed_attack_no_evade(self, setup):
        """攻击失败：不躲避。"""
        state, bus, bag, engine, inv = setup
        bag.tokens = [ChaosTokenType.AUTO_FAIL]
        result = engine.run_test(
            investigator_id="inv1", skill_type=Skill.COMBAT,
            difficulty=3, committed_card_ids=["stunning_blow_lv0"],
        )
        assert not result.success
        enemy = state.get_card_instance("enemy_1")
        assert not enemy.exhausted
        assert "enemy_1" in inv.threat_area

    def test_non_combat_test_no_evade(self, setup):
        """非战斗检定成功：不躲避。"""
        state, bus, bag, engine, inv = setup
        bag.tokens = [ChaosTokenType.ZERO]
        result = engine.run_test(
            investigator_id="inv1", skill_type=Skill.AGILITY,
            difficulty=2, committed_card_ids=["stunning_blow_lv0"],
        )
        assert result.success
        assert "enemy_1" in inv.threat_area
