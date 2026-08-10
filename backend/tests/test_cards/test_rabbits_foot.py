"""Tests for Rabbit's Foot (Level 0)."""

import pytest
from backend.cards.survivor.rabbits_foot_lv0 import RabbitsFoot
from backend.engine.event_bus import EventBus
from backend.engine.skill_test import SkillTestEngine
from backend.models.chaos import ChaosBag
from backend.models.enums import ChaosTokenType, PlayerClass, Skill, SlotType
from backend.models.state import CardInstance, GameState, InvestigatorState, ScenarioState
from backend.tests.conftest import make_investigator_data, make_asset_data, make_skill_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()
    bag = ChaosBag()
    bag.seed(42)

    inv_data = make_investigator_data(willpower=2)
    state.card_database[inv_data.id] = inv_data

    inv = InvestigatorState(
        investigator_id="inv1",
        card_data=inv_data,
        location_id="loc1",
        deck=["card_a", "card_b", "card_c"],
    )
    inv.play_area.append("rabbits_foot_inst")
    state.investigators["inv1"] = inv
    state.cards_in_play["rabbits_foot_inst"] = CardInstance(
        instance_id="rabbits_foot_inst", card_id="rabbits_foot_lv0",
        owner_id="inv1", controller_id="inv1",
        slot_used=[SlotType.ACCESSORY],
    )

    engine = SkillTestEngine(state, bus, bag)

    impl = RabbitsFoot("rabbits_foot_inst")
    impl.register(bus, "rabbits_foot_inst")

    return state, bus, bag, engine, inv


class TestRabbitsFoot:
    def test_draw_on_fail(self, setup):
        state, bus, bag, engine, inv = setup
        bag.tokens = [ChaosTokenType.AUTO_FAIL]
        initial_deck = len(inv.deck)

        engine.run_test(
            investigator_id="inv1",
            skill_type=Skill.WILLPOWER,
            difficulty=3,
        )
        # Should draw 1 card on failure
        assert len(inv.deck) == initial_deck - 1

    def test_no_draw_on_success(self, setup):
        state, bus, bag, engine, inv = setup
        bag.tokens = [ChaosTokenType.PLUS_1]
        initial_deck = len(inv.deck)

        engine.run_test(
            investigator_id="inv1",
            skill_type=Skill.WILLPOWER,
            difficulty=2,
        )
        # Should not draw on success
        assert len(inv.deck) == initial_deck

    def test_exhausts_after_trigger(self, setup):
        """卡面：失败后横置兔脚才抽牌——横置后再次失败不重复抽。"""
        state, bus, bag, engine, inv = setup
        inst = state.cards_in_play["rabbits_foot_inst"]
        bag.tokens = [ChaosTokenType.AUTO_FAIL]

        engine.run_test(
            investigator_id="inv1", skill_type=Skill.WILLPOWER, difficulty=3,
        )
        assert inst.exhausted is True
        assert len(inv.deck) == 2

        # 已横置：第二次失败不再抽
        bag.tokens = [ChaosTokenType.AUTO_FAIL]
        engine.run_test(
            investigator_id="inv1", skill_type=Skill.WILLPOWER, difficulty=3,
        )
        assert len(inv.deck) == 2

        # 刷新后可再次触发
        inst.exhausted = False
        bag.tokens = [ChaosTokenType.AUTO_FAIL]
        engine.run_test(
            investigator_id="inv1", skill_type=Skill.WILLPOWER, difficulty=3,
        )
        assert len(inv.deck) == 1
