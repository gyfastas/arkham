"""Tests for Hiking Boots (Level 1)."""

import pytest
from backend.cards.seeker.hiking_boots_lv1 import HikingBoots
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

    inv_data = make_investigator_data(agility=2)
    state.card_database[inv_data.id] = inv_data
    for loc_id, conns, clues, revealed in [
        ("loc_a", ["loc_b", "loc_c"], 0, True),
        ("loc_b", ["loc_a"], 2, True),
        ("loc_c", ["loc_a"], 0, False),
    ]:
        loc_data = make_location_data(id=loc_id, connections=conns)
        state.card_database[loc_id] = loc_data
        state.locations[loc_id] = LocationState(
            location_id=loc_id, card_data=loc_data, clues=clues, revealed=revealed,
        )

    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc_a",
    )
    state.investigators["inv1"] = inv

    inst = CardInstance(
        instance_id="boots_1", card_id="hiking_boots_lv1",
        owner_id="inv1", controller_id="inv1",
    )
    state.cards_in_play["boots_1"] = inst
    inv.play_area.append("boots_1")

    impl = HikingBoots("boots_1")
    impl.register(bus, "boots_1")
    return state, bus, inv, inst, impl


def _last_clue(state, bus):
    ctx = EventContext(
        game_state=state, event=GameEvent.CLUE_DISCOVERED,
        investigator_id="inv1", location_id="loc_a", amount=1,
    )
    bus.emit(ctx)
    return ctx


class TestHikingBoots:
    def test_agility_bonus(self, setup):
        """常驻 +1 敏捷。"""
        state, bus, inv, inst, impl = setup
        ctx = EventContext(
            game_state=state, event=GameEvent.SKILL_VALUE_DETERMINED,
            investigator_id="inv1", skill_type=Skill.AGILITY, amount=2,
        )
        bus.emit(ctx)
        assert ctx.amount == 3

    def test_move_to_clued_connection_after_last_clue(self, setup):
        """地点最后1个线索被发现后：消耗并移动到有线索的连接地点。"""
        state, bus, inv, inst, impl = setup
        ctx = _last_clue(state, bus)
        assert ctx.extra["hiking_boots_moved"] == "loc_b"
        assert inv.location_id == "loc_b"
        assert inst.exhausted is True

    def test_falls_back_to_unrevealed_connection(self, setup):
        """无有线索连接地点时：移动到未揭示连接地点。"""
        state, bus, inv, inst, impl = setup
        state.locations["loc_b"].clues = 0
        ctx = _last_clue(state, bus)
        assert ctx.extra["hiking_boots_moved"] == "loc_c"

    def test_no_valid_destination_no_exhaust(self, setup):
        """无合法目的地：不消耗不移动。"""
        state, bus, inv, inst, impl = setup
        state.locations["loc_b"].clues = 0
        state.locations["loc_c"].revealed = True
        ctx = _last_clue(state, bus)
        assert "hiking_boots_moved" not in ctx.extra
        assert inst.exhausted is False
        assert inv.location_id == "loc_a"
