"""Tests for Try and Try Again (Level 1)."""

import pytest
from backend.cards.survivor.try_and_try_again_lv1 import TryAndTryAgain
from backend.engine.event_bus import EventBus
from backend.engine.skill_test import SkillTestEngine
from backend.models.chaos import ChaosBag
from backend.models.enums import ChaosTokenType, Skill
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, ScenarioState,
)
from backend.tests.conftest import make_investigator_data, make_skill_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()
    bag = ChaosBag()
    bag.seed(42)

    inv_data = make_investigator_data(willpower=3)
    state.card_database[inv_data.id] = inv_data
    state.card_database["guts_lv0"] = make_skill_data(
        id="guts_lv0", skill_icons={"willpower": 2})

    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1",
        hand=["guts_lv0"],
    )
    state.investigators["inv1"] = inv

    # 源数据 uses 键为笔误 "triess"：按线上数据初始化，验证兼容
    inst = CardInstance(
        instance_id="tata_inst", card_id="try_and_try_again_lv1",
        owner_id="inv1", controller_id="inv1", uses={"triess": 3},
    )
    state.cards_in_play["tata_inst"] = inst
    inv.play_area.append("tata_inst")

    engine = SkillTestEngine(state, bus, bag)
    impl = TryAndTryAgain("tata_inst")
    impl.register(bus, "tata_inst")
    return state, bus, bag, engine, inv, inst


def _fail_with_guts(engine, bag):
    bag.tokens = [ChaosTokenType.AUTO_FAIL]
    return engine.run_test(
        investigator_id="inv1", skill_type=Skill.WILLPOWER,
        difficulty=5, committed_card_ids=["guts_lv0"],
    )


class TestTryAndTryAgain:
    def test_returns_committed_skill_on_failure(self, setup):
        """检定失败：消耗+1次数，投入的技能卡返回手牌。"""
        state, bus, bag, engine, inv, inst = setup
        result = _fail_with_guts(engine, bag)
        assert not result.success
        assert inst.exhausted
        assert inst.uses["triess"] == 2
        assert "guts_lv0" in inv.hand
        assert "guts_lv0" not in inv.discard

    def test_no_return_on_success(self, setup):
        """检定成功：不触发。"""
        state, bus, bag, engine, inv, inst = setup
        bag.tokens = [ChaosTokenType.ZERO]
        result = engine.run_test(
            investigator_id="inv1", skill_type=Skill.WILLPOWER,
            difficulty=5, committed_card_ids=["guts_lv0"],
        )
        assert result.success  # 3 + 2 + 0 = 5
        assert not inst.exhausted
        assert inst.uses["triess"] == 3
        assert "guts_lv0" in inv.discard  # 正常弃置

    def test_no_skill_committed_no_trigger(self, setup):
        """未投入技能卡：不触发。"""
        state, bus, bag, engine, inv, inst = setup
        bag.tokens = [ChaosTokenType.AUTO_FAIL]
        result = engine.run_test(
            investigator_id="inv1", skill_type=Skill.WILLPOWER, difficulty=5,
        )
        assert not result.success
        assert not inst.exhausted
        assert inst.uses["triess"] == 3

    def test_discarded_when_tries_run_out(self, setup):
        """次数耗尽：本卡被丢弃。"""
        state, bus, bag, engine, inv, inst = setup
        inst.uses["triess"] = 1
        _fail_with_guts(engine, bag)
        assert inst.uses["triess"] == 0
        assert "tata_inst" not in inv.play_area
        assert state.get_card_instance("tata_inst") is None
        assert "try_and_try_again_lv1" in inv.discard
        assert "guts_lv0" in inv.hand
