"""Tests for Blur (Level 1 / Level 4)."""

import pytest
from backend.cards.rogue.blur_lv1 import BlurLv1
from backend.cards.rogue.blur_lv4 import BlurLv4
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent, Skill
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, ScenarioState,
)
from backend.tests.conftest import make_investigator_data


@pytest.fixture
def setup_lv1():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()
    inv_data = make_investigator_data(willpower=5, agility=3)
    state.card_database[inv_data.id] = inv_data
    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1",
    )
    inv.actions_remaining = 3
    state.investigators["inv1"] = inv

    impl = BlurLv1("blur_inst")
    impl.register(bus, "blur_inst")
    ci = CardInstance(
        instance_id="blur_inst", card_id="blur_lv1",
        owner_id="inv1", controller_id="inv1",
        uses={"chargess": 3},  # 数据笔误键名，实现应兼容
    )
    state.cards_in_play["blur_inst"] = ci
    inv.play_area.append("blur_inst")
    return state, bus, inv, impl, ci


def _value_ctx(state, amount=3):
    return EventContext(
        game_state=state,
        event=GameEvent.SKILL_VALUE_DETERMINED,
        investigator_id="inv1",
        skill_type=Skill.AGILITY,
        amount=amount,
        extra={"base_skill": 3},
    )


class TestBlurLv1:
    def test_activate_requires_charges(self, setup_lv1):
        state, bus, inv, impl, ci = setup_lv1
        assert impl.activate(state, "inv1") is True
        ci.uses["charges"] = 0
        assert impl.activate(state, "inv1") is False

    def test_willpower_substitution_and_bonus(self, setup_lv1):
        """意志(5)高于敏捷(3)：替换并+1 → 3+(5-3)+1=6。"""
        state, bus, inv, impl, ci = setup_lv1
        impl.activate(state, "inv1")
        ctx = _value_ctx(state)
        bus.emit(ctx)
        assert ctx.amount == 6

    def test_success_spends_charge_grants_action(self, setup_lv1):
        """成功：花费1充能，本回合+1行动（chargess 键被规整）。"""
        state, bus, inv, impl, ci = setup_lv1
        impl.activate(state, "inv1")
        ctx = EventContext(
            game_state=state,
            event=GameEvent.SKILL_TEST_SUCCESSFUL,
            investigator_id="inv1",
            skill_type=Skill.AGILITY,
            success=True, modified_skill=5, difficulty=3,
        )
        bus.emit(ctx)
        assert ci.uses.get("charges") == 2  # 3-1（chargess 已规整为 charges）
        assert "chargess" not in ci.uses
        assert inv.actions_remaining == 4
        assert ctx.extra["blur_extra_actions"] == 1

    def test_succeed_by_zero_takes_damage(self, setup_lv1):
        """成功且恰等于难度：受到1点伤害。"""
        state, bus, inv, impl, ci = setup_lv1
        impl.activate(state, "inv1")
        ctx = EventContext(
            game_state=state,
            event=GameEvent.SKILL_TEST_SUCCESSFUL,
            investigator_id="inv1",
            skill_type=Skill.AGILITY,
            success=True, modified_skill=3, difficulty=3,
        )
        bus.emit(ctx)
        assert inv.damage == 1
        assert ctx.extra["blur_zero_margin_damage"] == 1

    def test_no_effect_when_not_armed(self, setup_lv1):
        state, bus, inv, impl, ci = setup_lv1
        ctx = _value_ctx(state)
        bus.emit(ctx)
        assert ctx.amount == 3


@pytest.fixture
def setup_lv4():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()
    inv_data = make_investigator_data(willpower=5, agility=3)
    state.card_database[inv_data.id] = inv_data
    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1",
    )
    inv.actions_remaining = 3
    state.investigators["inv1"] = inv

    impl = BlurLv4("blur4_inst")
    impl.register(bus, "blur4_inst")
    ci = CardInstance(
        instance_id="blur4_inst", card_id="blur_lv4",
        owner_id="inv1", controller_id="inv1",
        uses={"chargess": 4},
    )
    state.cards_in_play["blur4_inst"] = ci
    inv.play_area.append("blur4_inst")
    return state, bus, inv, impl, ci


class TestBlurLv4:
    def test_skill_bonus_two(self, setup_lv4):
        """+2技能值（意志替换自动取高）：3+(5-3)+2=7。"""
        state, bus, inv, impl, ci = setup_lv4
        impl.activate(state, "inv1")
        ctx = _value_ctx(state)
        bus.emit(ctx)
        assert ctx.amount == 7

    def test_success_spends_two_charges_two_actions(self, setup_lv4):
        """成功：自动花费2充能，获得2个额外行动。"""
        state, bus, inv, impl, ci = setup_lv4
        impl.activate(state, "inv1")
        ctx = EventContext(
            game_state=state,
            event=GameEvent.SKILL_TEST_SUCCESSFUL,
            investigator_id="inv1",
            skill_type=Skill.AGILITY,
            success=True, modified_skill=6, difficulty=3,
        )
        bus.emit(ctx)
        assert ci.uses["charges"] == 2
        assert inv.actions_remaining == 5
        assert ctx.extra["blur_extra_actions"] == 2

    def test_succeed_by_zero_takes_two_damage(self, setup_lv4):
        state, bus, inv, impl, ci = setup_lv4
        impl.activate(state, "inv1")
        ctx = EventContext(
            game_state=state,
            event=GameEvent.SKILL_TEST_SUCCESSFUL,
            investigator_id="inv1",
            skill_type=Skill.AGILITY,
            success=True, modified_skill=3, difficulty=3,
        )
        bus.emit(ctx)
        assert inv.damage == 2

    def test_partial_charges_cap_actions(self, setup_lv4):
        """仅剩1充能：只花1个，只得1个额外行动。"""
        state, bus, inv, impl, ci = setup_lv4
        ci.uses["chargess"] = 1
        impl.activate(state, "inv1")
        ctx = EventContext(
            game_state=state,
            event=GameEvent.SKILL_TEST_SUCCESSFUL,
            investigator_id="inv1",
            skill_type=Skill.AGILITY,
            success=True, modified_skill=6, difficulty=3,
        )
        bus.emit(ctx)
        assert ci.uses.get("charges") == 0
        assert inv.actions_remaining == 4
