"""Tests for Otherworldly Compass (Level 2)."""

import pytest
from backend.cards.seeker.otherworldly_compass_lv2 import OtherworldlyCompass
from backend.engine.event_bus import EventBus
from backend.models.chaos import ChaosBag
from backend.models.enums import ChaosTokenType
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, LocationState, ScenarioState,
)
from backend.tests.conftest import make_investigator_data, make_location_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()
    bag = ChaosBag()
    bag.seed(42)

    inv_data = make_investigator_data(intellect=3)
    state.card_database[inv_data.id] = inv_data
    for loc_id, conns, revealed in [
        ("loc_a", ["loc_b", "loc_c", "loc_d"], True),
        ("loc_b", ["loc_a"], True),
        ("loc_c", ["loc_a"], True),
        ("loc_d", ["loc_a"], False),
    ]:
        loc_data = make_location_data(id=loc_id, shroud=5, connections=conns)
        state.card_database[loc_id] = loc_data
        state.locations[loc_id] = LocationState(
            location_id=loc_id, card_data=loc_data, clues=2, revealed=revealed,
        )

    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc_a",
    )
    state.investigators["inv1"] = inv

    inst = CardInstance(
        instance_id="comp_1", card_id="otherworldly_compass_lv2",
        owner_id="inv1", controller_id="inv1",
    )
    state.cards_in_play["comp_1"] = inst
    inv.play_area.append("comp_1")

    impl = OtherworldlyCompass("comp_1")
    impl.register(bus, "comp_1")
    impl.bind_chaos_bag(bag)
    return state, bus, bag, inv, inst, impl


class TestOtherworldlyCompass:
    def test_shroud_reduced_by_revealed_connections(self, setup):
        """隐蔽值5 - 2个已揭示连接 = 难度3：智力3+0标记恰好成功，发现1线索。"""
        state, bus, bag, inv, inst, impl = setup
        bag.tokens = [ChaosTokenType.ZERO]
        loc = state.locations["loc_a"]

        assert impl.activate(state, "inv1") is True
        assert inv.clues == 1
        assert loc.clues == 1
        assert inst.exhausted is True

    def test_fails_without_reduction(self, setup):
        """对照：连接地点未揭示时不减隐蔽值，3<5 失败。"""
        state, bus, bag, inv, inst, impl = setup
        state.locations["loc_b"].revealed = False
        state.locations["loc_c"].revealed = False
        bag.tokens = [ChaosTokenType.ZERO]

        impl.activate(state, "inv1")
        assert inv.clues == 0
        assert state.locations["loc_a"].clues == 2
