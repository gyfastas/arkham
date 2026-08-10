"""Tests for Tennessee Sour Mash (Level 3)."""

import pytest
from backend.cards.survivor.tennessee_sour_mash_lv3 import TennesseeSourMash
from backend.engine.event_bus import EventBus
from backend.engine.skill_test import SkillTestEngine
from backend.models.chaos import ChaosBag
from backend.models.enums import ChaosTokenType, Skill
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
    bag = ChaosBag()
    bag.seed(42)

    inv_data = make_investigator_data(willpower=3, combat=3)
    state.card_database[inv_data.id] = inv_data
    enemy_data = make_enemy_data(fight=6)
    state.card_database[enemy_data.id] = enemy_data
    elite_data = make_enemy_data(id="elite_enemy", fight=6, keywords=["elite"])
    state.card_database[elite_data.id] = elite_data
    loc_data = make_location_data()
    state.card_database[loc_data.id] = loc_data

    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data,
        location_id="test_location",
    )
    state.investigators["inv1"] = inv
    state.locations["test_location"] = LocationState(
        location_id="test_location", card_data=loc_data)

    # 源数据 uses 键为笔误 "suppliess"：按线上数据初始化，验证兼容
    inst = CardInstance(
        instance_id="tsm_inst", card_id="tennessee_sour_mash_lv3",
        owner_id="inv1", controller_id="inv1",
        uses={"suppliess": 3},
    )
    state.cards_in_play["tsm_inst"] = inst
    inv.play_area.append("tsm_inst")

    state.cards_in_play["enemy_1"] = CardInstance(
        instance_id="enemy_1", card_id="test_enemy",
        owner_id="scenario", controller_id="scenario",
    )
    inv.threat_area.append("enemy_1")

    engine = SkillTestEngine(state, bus, bag)
    impl = TennesseeSourMash("tsm_inst")
    impl.register(bus, "tsm_inst")
    return state, bus, bag, engine, inv, inst, impl


class TestWillpowerBoost:
    def test_spends_supply_and_boosts(self, setup):
        """花1补给：下一次意志检定+2。"""
        state, bus, bag, engine, inv, inst, impl = setup
        bag.tokens = [ChaosTokenType.ZERO]
        ok = impl.activate_willpower(state, "inv1")
        assert ok
        assert inst.uses["suppliess"] == 2
        assert inst.exhausted
        result = engine.run_test(
            investigator_id="inv1", skill_type=Skill.WILLPOWER, difficulty=5,
        )
        # 3 + 2 + 0 = 5 >= 5
        assert result.success
        assert result.extra["asset_bonus"] == 2

    def test_no_supplies_no_activation(self, setup):
        state, bus, bag, engine, inv, inst, impl = setup
        inst.uses["suppliess"] = 0
        assert impl.activate_willpower(state, "inv1") is False


class TestFight:
    def test_fight_discards_and_boosts_3(self, setup):
        """丢弃本卡攻击：+3战斗。"""
        state, bus, bag, engine, inv, inst, impl = setup
        bag.tokens = [ChaosTokenType.ZERO]
        ok = impl.activate_fight(state, "inv1", "enemy_1")
        assert ok
        assert "tsm_inst" not in inv.play_area
        assert "tennessee_sour_mash_lv3" in inv.discard

        result = engine.run_test(
            investigator_id="inv1", skill_type=Skill.COMBAT,
            difficulty=6, source_instance_id="tsm_inst",
        )
        # 3 + 3 + 0 = 6 >= 6
        assert result.success
        # 非精英目标：自动躲避
        enemy = state.get_card_instance("enemy_1")
        loc = state.get_location("test_location")
        assert enemy.exhausted
        assert "enemy_1" not in inv.threat_area
        assert "enemy_1" in loc.enemies

    def test_fight_vs_elite_no_evade(self, setup):
        """目标为精英：不自动躲避。"""
        state, bus, bag, engine, inv, inst, impl = setup
        bag.tokens = [ChaosTokenType.ZERO]
        state.cards_in_play["elite_1"] = CardInstance(
            instance_id="elite_1", card_id="elite_enemy",
            owner_id="scenario", controller_id="scenario",
        )
        inv.threat_area.append("elite_1")

        impl.activate_fight(state, "inv1", "elite_1")
        result = engine.run_test(
            investigator_id="inv1", skill_type=Skill.COMBAT,
            difficulty=6, source_instance_id="tsm_inst",
        )
        assert result.success
        elite = state.get_card_instance("elite_1")
        assert not elite.exhausted
        assert "elite_1" in inv.threat_area

    def test_failed_fight_no_evade(self, setup):
        """攻击失败：不躲避。"""
        state, bus, bag, engine, inv, inst, impl = setup
        bag.tokens = [ChaosTokenType.AUTO_FAIL]
        impl.activate_fight(state, "inv1", "enemy_1")
        result = engine.run_test(
            investigator_id="inv1", skill_type=Skill.COMBAT,
            difficulty=6, source_instance_id="tsm_inst",
        )
        assert not result.success
        assert "enemy_1" in inv.threat_area
