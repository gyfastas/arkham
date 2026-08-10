"""Tests for Esoteric Atlas (Level 1)."""

import pytest
from backend.cards.seeker.esoteric_atlas_lv1 import EsotericAtlas
from backend.engine.event_bus import EventBus
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, LocationState, ScenarioState,
)
from backend.tests.conftest import make_investigator_data, make_location_data


@pytest.fixture
def setup():
    """地点链 A—B—C（C 已揭示），另有 A—D（D 已揭示，距离1）。"""
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()

    inv_data = make_investigator_data()
    state.card_database[inv_data.id] = inv_data
    for loc_id, conns, revealed in [
        ("loc_a", ["loc_b", "loc_d"], True),
        ("loc_b", ["loc_a", "loc_c"], True),
        ("loc_c", ["loc_b"], True),
        ("loc_d", ["loc_a"], True),
    ]:
        loc_data = make_location_data(id=loc_id, connections=conns)
        state.card_database[loc_id] = loc_data
        state.locations[loc_id] = LocationState(
            location_id=loc_id, card_data=loc_data, revealed=revealed,
        )

    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc_a",
    )
    state.investigators["inv1"] = inv

    inst = CardInstance(
        instance_id="atlas_1", card_id="esoteric_atlas_lv1",
        owner_id="inv1", controller_id="inv1",
    )
    inst.uses = {"secretss": 4}  # 生产数据的双 s 键
    state.cards_in_play["atlas_1"] = inst
    inv.play_area.append("atlas_1")

    impl = EsotericAtlas("atlas_1")
    impl.register(bus, "atlas_1")
    return state, bus, inv, inst, impl


class TestEsotericAtlas:
    def test_move_two_connections_away(self, setup):
        """花1秘密+消耗：移动到最短距离恰好为2的已揭示地点。"""
        state, bus, inv, inst, impl = setup
        assert impl.activate(state, "inv1") is True
        assert inv.location_id == "loc_c"
        assert inst.uses["secretss"] == 3
        assert inst.exhausted is True

    def test_explicit_target_validation(self, setup):
        """显式目标：距离1或不可达的地点被拒绝。"""
        state, bus, inv, inst, impl = setup
        assert impl.activate(state, "inv1", target_location_id="loc_b") is False
        assert impl.activate(state, "inv1", target_location_id="loc_d") is False
        assert impl.activate(state, "inv1", target_location_id="loc_c") is True
        assert inv.location_id == "loc_c"

    def test_unrevealed_destination_not_offered(self, setup):
        """距离2但未揭示的地点不可作为目的地。"""
        state, bus, inv, inst, impl = setup
        state.locations["loc_c"].revealed = False
        assert impl.activate(state, "inv1") is False
        assert inv.location_id == "loc_a"

    def test_no_secrets_no_move(self, setup):
        """无秘密时不能发动。"""
        state, bus, inv, inst, impl = setup
        inst.uses = {"secretss": 0}
        assert impl.activate(state, "inv1") is False
        assert inv.location_id == "loc_a"
