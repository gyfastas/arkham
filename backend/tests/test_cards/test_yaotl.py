"""Tests for Yaotl (Level 1)."""

import pytest
from backend.cards.survivor.yaotl_lv1 import Yaotl
from backend.engine.event_bus import EventBus
from backend.engine.skill_test import SkillTestEngine
from backend.models.chaos import ChaosBag
from backend.models.enums import ChaosTokenType, Phase, Skill
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, ScenarioState,
)
from backend.tests.conftest import (
    make_asset_data, make_investigator_data, make_skill_data,
)


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()
    bag = ChaosBag()
    bag.seed(42)
    state.scenario.current_phase = Phase.INVESTIGATION
    state.scenario.round_number = 1

    inv_data = make_investigator_data(combat=3)
    state.card_database[inv_data.id] = inv_data
    # 弃牌堆顶卡：2战斗1意志图标（含1万能，不计入）
    state.card_database["top_card"] = make_skill_data(
        id="top_card", skill_icons={"combat": 2, "willpower": 1, "wild": 1})

    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1",
        discard=["top_card"], deck=["deck_a", "deck_b"],
    )
    state.investigators["inv1"] = inv

    inst = CardInstance(
        instance_id="yaotl_inst", card_id="yaotl_lv1",
        owner_id="inv1", controller_id="inv1",
    )
    state.cards_in_play["yaotl_inst"] = inst
    inv.play_area.append("yaotl_inst")

    engine = SkillTestEngine(state, bus, bag)
    impl = Yaotl("yaotl_inst")
    impl.register(bus, "yaotl_inst")
    return state, bus, bag, engine, inv, inst, impl


class TestYaotlBoost:
    def test_boost_from_discard_top_icons(self, setup):
        """消耗后：战斗检定 +2（弃牌堆顶卡的战斗图标数）。"""
        state, bus, bag, engine, inv, inst, impl = setup
        bag.tokens = [ChaosTokenType.ZERO]
        assert impl.activate_boost(state, "inv1") is True
        assert inst.exhausted
        result = engine.run_test(
            investigator_id="inv1", skill_type=Skill.COMBAT, difficulty=5,
        )
        # 3 + 2 + 0 = 5
        assert result.modified_skill == 5
        assert result.success

    def test_boost_ignores_wild_icons(self, setup):
        """万能图标不计入：敏捷检定 +0。"""
        state, bus, bag, engine, inv, inst, impl = setup
        bag.tokens = [ChaosTokenType.ZERO]
        impl.activate_boost(state, "inv1")
        result = engine.run_test(
            investigator_id="inv1", skill_type=Skill.AGILITY, difficulty=3,
        )
        # 顶卡无敏捷图标（仅1万能不能算）：3 + 0 + 0 = 3
        assert result.modified_skill == 3
        assert result.success

    def test_boost_requires_discard_pile(self, setup):
        """弃牌堆为空时无法启动。"""
        state, bus, bag, engine, inv, inst, impl = setup
        inv.discard = []
        assert impl.activate_boost(state, "inv1") is False
        assert not inst.exhausted


class TestYaotlMill:
    def test_mill_discards_deck_top(self, setup):
        """磨牌：丢弃牌堆顶1张。"""
        state, bus, bag, engine, inv, inst, impl = setup
        assert impl.activate_mill(state, "inv1") is True
        assert inv.deck == ["deck_b"]
        assert inv.discard[-1] == "deck_a"

    def test_mill_limited_once_per_phase(self, setup):
        """每阶段限1次：同阶段第二次失败；进入新阶段后恢复。"""
        state, bus, bag, engine, inv, inst, impl = setup
        assert impl.activate_mill(state, "inv1") is True
        assert impl.activate_mill(state, "inv1") is False
        assert inv.deck == ["deck_b"]
        state.scenario.current_phase = Phase.ENEMY
        assert impl.activate_mill(state, "inv1") is True
        assert inv.deck == []
