"""Tests for The Red Clock (Level 2 & Level 5)."""

import pytest

from backend.cards.rogue.the_red_clock_lv2 import TheRedClockLv2
from backend.cards.rogue.the_red_clock_lv5 import TheRedClockLv5
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent, Skill
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, ScenarioState,
)
from backend.tests.conftest import make_investigator_data


def _make(bus, cls, card_id):
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    inv_data = make_investigator_data()
    state.card_database[inv_data.id] = inv_data
    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1")
    inv.resources = 0
    inv.actions_remaining = 3
    state.investigators["inv1"] = inv
    inst = CardInstance(
        instance_id="clock_inst", card_id=card_id,
        owner_id="inv1", controller_id="inv1", uses={"charges": 0},
    )
    state.cards_in_play["clock_inst"] = inst
    inv.play_area.append("clock_inst")
    impl = cls("clock_inst")
    impl.register(bus, "clock_inst")
    return state, inv, inst, impl


def _turn_begins(bus, state):
    ctx = EventContext(
        game_state=state,
        event=GameEvent.INVESTIGATOR_TURN_BEGINS,
        investigator_id="inv1",
    )
    bus.emit(ctx)
    return ctx


def _skill_value(bus, state, amount=3):
    ctx = EventContext(
        game_state=state,
        event=GameEvent.SKILL_VALUE_DETERMINED,
        investigator_id="inv1",
        skill_type=Skill.INTELLECT,
        amount=amount,
    )
    bus.emit(ctx)
    return ctx


class TestTheRedClockLv2:
    @pytest.fixture
    def setup(self):
        bus = EventBus()
        return (bus,) + _make(bus, TheRedClockLv2, "the_red_clock_lv2")

    def test_one_charge_arms_skill_bonus(self, setup):
        bus, state, inv, inst, impl = setup
        ctx = _turn_begins(bus, state)
        assert inst.uses["charges"] == 1
        assert ctx.extra["red_clock_skill_bonus"] == 3
        # 下次检定 +3，之后消耗
        ctx2 = _skill_value(bus, state)
        assert ctx2.amount == 6
        ctx3 = _skill_value(bus, state)
        assert ctx3.amount == 3

    def test_two_charges_free_moves_marker(self, setup):
        bus, state, inv, inst, impl = setup
        inst.uses["charges"] = 1
        ctx = _turn_begins(bus, state)
        assert inst.uses["charges"] == 2
        assert ctx.extra["red_clock_free_moves"] == 2

    def test_three_charges_bonus_action(self, setup):
        bus, state, inv, inst, impl = setup
        inst.uses["charges"] = 2
        ctx = _turn_begins(bus, state)
        assert inst.uses["charges"] == 3
        assert inv.actions_remaining == 4
        assert ctx.extra["red_clock_bonus_actions"] == 1

    def test_take_resources_at_three(self, setup):
        bus, state, inv, inst, impl = setup
        inst.uses["charges"] = 3
        ctx = _turn_begins(bus, state)
        assert ctx.extra["red_clock_took_resources"] == 3
        assert inv.resources == 3
        assert inst.uses["charges"] == 0  # lv2：取走后不再放置


class TestTheRedClockLv5:
    @pytest.fixture
    def setup(self):
        bus = EventBus()
        return (bus,) + _make(bus, TheRedClockLv5, "the_red_clock_lv5")

    def test_one_charge_arms_plus_four(self, setup):
        bus, state, inv, inst, impl = setup
        ctx = _turn_begins(bus, state)
        assert inst.uses["charges"] == 1
        assert ctx.extra["red_clock_skill_bonus"] == 4
        ctx2 = _skill_value(bus, state)
        assert ctx2.amount == 7

    def test_three_charges_two_bonus_actions(self, setup):
        bus, state, inv, inst, impl = setup
        inst.uses["charges"] = 2
        ctx = _turn_begins(bus, state)
        assert inst.uses["charges"] == 3
        assert inv.actions_remaining == 5
        assert ctx.extra["red_clock_bonus_actions"] == 2

    def test_take_then_place_lands_on_one(self, setup):
        """lv5：3充能时取走作为资源，随后仍放置1充能 → 正好1充能（+4武装）。"""
        bus, state, inv, inst, impl = setup
        inst.uses["charges"] = 3
        ctx = _turn_begins(bus, state)
        assert ctx.extra["red_clock_took_resources"] == 3
        assert inv.resources == 3
        assert inst.uses["charges"] == 1
        assert ctx.extra["red_clock_skill_bonus"] == 4
