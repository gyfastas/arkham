"""Tests for Unrelenting (Level 1)."""

import pytest
from backend.cards.survivor.unrelenting_lv1 import Unrelenting
from backend.engine.event_bus import EventBus
from backend.engine.skill_test import SkillTestEngine
from backend.models.chaos import ChaosBag
from backend.models.enums import ChaosTokenType, Skill
from backend.models.state import GameState, InvestigatorState, ScenarioState
from backend.tests.conftest import make_investigator_data, make_skill_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()
    bag = ChaosBag()
    bag.seed(42)

    inv_data = make_investigator_data(combat=3)
    state.card_database[inv_data.id] = inv_data
    state.card_database["unrelenting_lv1"] = make_skill_data(
        id="unrelenting_lv1", skill_icons={"wild": 1})

    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1",
        hand=["unrelenting_lv1"], deck=["card_a", "card_b"],
    )
    state.investigators["inv1"] = inv

    engine = SkillTestEngine(state, bus, bag)
    impl = Unrelenting("unr_inst")
    impl.register(bus, "unr_inst")
    impl.bind_chaos_bag(bag)
    return state, bus, bag, engine, inv, impl


class TestUnrelenting:
    def test_seals_three_worst_tokens(self, setup):
        """投入后：封印袋中最差的3个非自动失败标记；本次检定抽不到它们。"""
        state, bus, bag, engine, inv, impl = setup
        bag.tokens = [
            ChaosTokenType.PLUS_1, ChaosTokenType.MINUS_1,
            ChaosTokenType.MINUS_2, ChaosTokenType.SKULL,
            ChaosTokenType.AUTO_FAIL,
        ]
        engine.run_test(
            investigator_id="inv1", skill_type=Skill.COMBAT,
            difficulty=3, committed_card_ids=["unrelenting_lv1"],
        )
        # 检定期间袋中最差3个被封印：skull(-3档)、-2、-1
        assert sorted(t.value for t in impl._sealed) == []  # 结束后已释放
        # 结束后全部释放回袋
        assert sorted(t.value for t in bag.tokens) == sorted(
            ["+1", "-1", "-2", "skull", "auto_fail"])
        # 未全为良标记：不抽牌
        assert inv.deck == ["card_a", "card_b"]

    def test_sealed_tokens_removed_during_test(self, setup):
        """封印生效于本次检定：袋中仅剩 +1（其余被封印），检定必然抽 +1。"""
        state, bus, bag, engine, inv, impl = setup
        bag.tokens = [
            ChaosTokenType.PLUS_1, ChaosTokenType.MINUS_1,
            ChaosTokenType.MINUS_2, ChaosTokenType.SKULL,
        ]
        result = engine.run_test(
            investigator_id="inv1", skill_type=Skill.COMBAT,
            difficulty=5, committed_card_ids=["unrelenting_lv1"],
        )
        # 3 最差被封印后袋中只剩 +1：3 + 1图标 + 1 = 5
        assert result.token == ChaosTokenType.PLUS_1
        assert result.success

    def test_all_good_sealed_draws_2(self, setup):
        """封足3个且全是 +1/0/bless/elder_sign：抽2张牌。"""
        state, bus, bag, engine, inv, impl = setup
        bag.tokens = [
            ChaosTokenType.PLUS_1, ChaosTokenType.ZERO,
            ChaosTokenType.BLESS, ChaosTokenType.ELDER_SIGN,
        ]
        engine.run_test(
            investigator_id="inv1", skill_type=Skill.COMBAT,
            difficulty=3, committed_card_ids=["unrelenting_lv1"],
        )
        # 最差3个为 0/+1/bless（全良）：抽2张；elder_sign 留在袋中
        assert "card_a" in inv.hand and "card_b" in inv.hand
        assert inv.deck == []
        # 结束后释放
        assert sorted(t.value for t in bag.tokens) == sorted(
            ["+1", "0", "bless", "elder_sign"])

    def test_not_committed_no_seal(self, setup):
        """未投入：不封印。"""
        state, bus, bag, engine, inv, impl = setup
        bag.tokens = [ChaosTokenType.MINUS_1, ChaosTokenType.MINUS_2]
        before = list(bag.tokens)
        engine.run_test(
            investigator_id="inv1", skill_type=Skill.COMBAT, difficulty=3,
        )
        assert sorted(t.value for t in bag.tokens) == sorted(
            t.value for t in before)
