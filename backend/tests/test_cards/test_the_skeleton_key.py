"""Tests for The Skeleton Key (Level 2)."""

import pytest

from backend.cards.rogue.the_skeleton_key_lv2 import TheSkeletonKey
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent, Skill
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, LocationState, ScenarioState,
)
from backend.tests.conftest import make_investigator_data, make_location_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()
    inv_data = make_investigator_data()
    state.card_database[inv_data.id] = inv_data
    loc_data = make_location_data(id="loc1", shroud=4)
    state.card_database["loc1"] = loc_data
    state.locations["loc1"] = LocationState(location_id="loc1", card_data=loc_data)
    loc2 = make_location_data(id="loc2", shroud=3)
    state.card_database["loc2"] = loc2
    state.locations["loc2"] = LocationState(location_id="loc2", card_data=loc2)
    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1")
    state.investigators["inv1"] = inv
    inst = CardInstance(
        instance_id="key_inst", card_id="the_skeleton_key_lv2",
        owner_id="inv1", controller_id="inv1",
    )
    state.cards_in_play["key_inst"] = inst
    inv.play_area.append("key_inst")
    impl = TheSkeletonKey("key_inst")
    impl.register(bus, "key_inst")
    return state, bus, inv, inst, impl


def _investigate_begins(bus, state, difficulty):
    ctx = EventContext(
        game_state=state,
        event=GameEvent.SKILL_TEST_BEGINS,
        investigator_id="inv1",
        skill_type=Skill.INTELLECT,
        difficulty=difficulty,
    )
    bus.emit(ctx)
    return ctx


class TestTheSkeletonKey:
    def test_attach_to_location(self, setup):
        state, bus, inv, inst, impl = setup
        assert impl.activate(state, "inv1") is True
        assert "key_inst" not in inv.play_area
        assert inst.attached_to == "loc1"
        assert "key_inst" in state.locations["loc1"].attachments

    def test_shroud_set_to_one_when_attached(self, setup):
        state, bus, inv, inst, impl = setup
        impl.activate(state, "inv1")
        ctx = _investigate_begins(bus, state, difficulty=4)
        assert ctx.difficulty == 1
        assert ctx.extra["skeleton_key_shroud_set"] is True

    def test_other_location_unaffected(self, setup):
        state, bus, inv, inst, impl = setup
        impl.activate(state, "inv1")
        inv.location_id = "loc2"
        ctx = _investigate_begins(bus, state, difficulty=3)
        assert ctx.difficulty == 3

    def test_detach_returns_to_play_area(self, setup):
        state, bus, inv, inst, impl = setup
        impl.activate(state, "inv1")
        assert impl.activate(state, "inv1") is True
        assert "key_inst" in inv.play_area
        assert inst.attached_to is None
        assert "key_inst" not in state.locations["loc1"].attachments
        # 取回后难度恢复正常
        ctx = _investigate_begins(bus, state, difficulty=4)
        assert ctx.difficulty == 4

    def test_non_intellect_test_unaffected(self, setup):
        state, bus, inv, inst, impl = setup
        impl.activate(state, "inv1")
        ctx = EventContext(
            game_state=state,
            event=GameEvent.SKILL_TEST_BEGINS,
            investigator_id="inv1",
            skill_type=Skill.COMBAT,
            difficulty=4,
        )
        bus.emit(ctx)
        assert ctx.difficulty == 4
