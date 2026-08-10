"""Tests for Abyssal Tome (Level 2). (07159)

消耗：攻击，可用智力或意志代替战斗；发动时可放1毁灭（最多3）；
每个毁灭+1技能值并+1伤害。
"""

import pytest
from backend.cards.mystic.abyssal_tome_lv2 import AbyssalTome
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent, Skill
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, ScenarioState,
)
from backend.tests.conftest import make_asset_data, make_investigator_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()
    inv_data = make_investigator_data(willpower=5, intellect=4, combat=2)
    state.card_database[inv_data.id] = inv_data
    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1",
    )
    state.investigators["inv1"] = inv
    state.card_database["abyssal_tome_lv2"] = make_asset_data(
        id="abyssal_tome_lv2", name="Abyssal Tome", traits=["item", "tome"],
    )
    inst = CardInstance(
        instance_id="inst_tome", card_id="abyssal_tome_lv2",
        owner_id="inv1", controller_id="inv1",
    )
    state.cards_in_play["inst_tome"] = inst
    inv.play_area.append("inst_tome")
    impl = AbyssalTome("inst_tome")
    impl.register(bus, "inst_tome")
    return state, bus, inv, inst, impl


def _combat_ctx(state, amount=2):
    return EventContext(
        game_state=state, event=GameEvent.SKILL_VALUE_DETERMINED,
        investigator_id="inv1", skill_type=Skill.COMBAT, amount=amount,
        source="inst_tome",
    )


class TestAbyssalTome:
    def test_activate_exhausts_and_places_doom(self, setup):
        state, bus, inv, inst, impl = setup
        assert impl.activate(state, "inv1", place_doom=True) is True
        assert inst.exhausted is True
        assert inst.doom == 1

    def test_doom_cap_3(self, setup):
        state, bus, inv, inst, impl = setup
        inst.doom = 3
        impl.activate(state, "inv1", place_doom=True)
        assert inst.doom == 3

    def test_intellect_substitute_with_doom_bonus(self, setup):
        """智力(4)代替战斗(2)，1毁灭再+1技能值。"""
        state, bus, inv, inst, impl = setup
        impl.activate(state, "inv1", skill=Skill.INTELLECT, place_doom=True)
        ctx = _combat_ctx(state)
        bus.emit(ctx)
        assert ctx.amount == 5  # 2 + (4-2) + 1

    def test_willpower_substitute(self, setup):
        state, bus, inv, inst, impl = setup
        impl.activate(state, "inv1", skill=Skill.WILLPOWER)
        ctx = _combat_ctx(state)
        bus.emit(ctx)
        assert ctx.amount == 5  # 2 + (5-2)，无毁灭

    def test_bonus_damage_per_doom(self, setup):
        state, bus, inv, inst, impl = setup
        inst.doom = 2
        impl.activate(state, "inv1")
        ctx = EventContext(
            game_state=state, event=GameEvent.SKILL_TEST_SUCCESSFUL,
            investigator_id="inv1", skill_type=Skill.COMBAT, success=True,
            source="inst_tome",
        )
        bus.emit(ctx)
        assert ctx.extra["bonus_damage"] == 2

    def test_exhausted_blocks_activate(self, setup):
        state, bus, inv, inst, impl = setup
        inst.exhausted = True
        assert impl.activate(state, "inv1") is False
