"""Tests for Seal of the Elder Sign (Level 5). (03312)

投入后本次检定的标记视为远古印记（取消自动失败、原标记修正清零）；
检定结束时从游戏中移除本卡。
"""

import pytest
from backend.cards.mystic.seal_of_the_elder_sign_lv5 import SealOfTheElderSign
from backend.cards.registry import CardRegistry
from backend.engine.event_bus import EventBus, EventContext
from backend.engine.skill_test import SkillTestEngine
from backend.models.chaos import ChaosBag
from backend.models.enums import ChaosTokenType, GameEvent, Skill
from backend.models.state import GameState, InvestigatorState, ScenarioState
from backend.tests.conftest import make_investigator_data, make_skill_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()
    bag = ChaosBag()
    bag.seed(42)

    inv_data = make_investigator_data(willpower=4)
    state.card_database[inv_data.id] = inv_data
    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1",
        hand=["seal_of_the_elder_sign_lv5"],
    )
    state.investigators["inv1"] = inv
    state.card_database["seal_of_the_elder_sign_lv5"] = make_skill_data(
        id="seal_of_the_elder_sign_lv5", name="Seal of the Elder Sign",
        skill_icons={"wild": 1},
    )

    registry = CardRegistry()
    registry.register_class(SealOfTheElderSign)
    engine = SkillTestEngine(state, bus, bag, card_registry=registry)
    return state, bus, bag, engine, inv


class TestSealOfTheElderSignEngine:
    def test_auto_fail_token_becomes_elder_sign(self, setup):
        """抽到自动失败也被视为远古印记：不自动失败，修正为0。"""
        state, bus, bag, engine, inv = setup
        bag.tokens = [ChaosTokenType.AUTO_FAIL]

        result = engine.run_test(
            investigator_id="inv1",
            skill_type=Skill.WILLPOWER,
            difficulty=3,
            committed_card_ids=["seal_of_the_elder_sign_lv5"],
        )
        assert not result.auto_fail
        # 意志4 + 野性图标1 + 印记修正0 = 5 >= 3
        assert result.success
        assert result.token_modifier == 0

    def test_negative_token_modifier_zeroed(self, setup):
        """-4 标记被清零：按基础技能+图标结算。"""
        state, bus, bag, engine, inv = setup
        bag.tokens = [ChaosTokenType.MINUS_4]

        result = engine.run_test(
            investigator_id="inv1",
            skill_type=Skill.WILLPOWER,
            difficulty=5,
            committed_card_ids=["seal_of_the_elder_sign_lv5"],
        )
        assert result.token_modifier == 0
        assert result.modified_skill == 5  # 4 + 1野性
        assert result.success

    def test_removed_from_game_after_test(self, setup):
        """检定结束时从游戏中移除（不在弃牌堆）。"""
        state, bus, bag, engine, inv = setup
        bag.tokens = [ChaosTokenType.ZERO]

        engine.run_test(
            investigator_id="inv1",
            skill_type=Skill.WILLPOWER,
            difficulty=1,
            committed_card_ids=["seal_of_the_elder_sign_lv5"],
        )
        assert "seal_of_the_elder_sign_lv5" not in inv.discard
        assert "seal_of_the_elder_sign_lv5" not in inv.hand
        assert state.scenario.vars["removed_from_game"] == [
            "seal_of_the_elder_sign_lv5"]


class TestSealOfTheElderSignUnit:
    def test_ctx_token_swapped_to_elder_sign(self, setup):
        """单元级：CHAOS_TOKEN_RESOLVED 的标记被改写为远古印记。"""
        state, bus, bag, engine, inv = setup
        impl = SealOfTheElderSign("inst_seal")
        impl.register(bus, "inst_seal")
        ctx = EventContext(
            game_state=state, event=GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="inv1", skill_type=Skill.WILLPOWER,
            chaos_token=ChaosTokenType.SKULL, amount=-2,
        )
        bus.emit(ctx)
        assert ctx.chaos_token == ChaosTokenType.ELDER_SIGN
        assert ctx.amount == 0
        assert ctx.extra["cancel_auto_fail"] is True
