"""Tests for Pendant of the Queen (Level 0)."""

import pytest
from backend.cards.seeker.pendant_of_the_queen_lv0 import PendantOfTheQueen
from backend.engine.event_bus import EventBus
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, LocationState, ScenarioState,
)
from backend.tests.conftest import (
    make_enemy_data, make_investigator_data, make_location_data,
)


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()

    inv_data = make_investigator_data()
    state.card_database[inv_data.id] = inv_data
    for loc_id, clues, revealed in [
        ("loc_a", 0, True), ("loc_b", 2, True),
    ]:
        loc_data = make_location_data(id=loc_id)
        state.card_database[loc_id] = loc_data
        state.locations[loc_id] = LocationState(
            location_id=loc_id, card_data=loc_data, clues=clues, revealed=revealed,
        )
    enemy_data = make_enemy_data()
    state.card_database["test_enemy"] = enemy_data
    enemy = CardInstance(
        instance_id="e1", card_id="test_enemy",
        owner_id="scenario", controller_id="scenario",
    )
    state.cards_in_play["e1"] = enemy
    state.locations["loc_b"].enemies.append("e1")

    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc_a",
    )
    state.investigators["inv1"] = inv

    inst = CardInstance(
        instance_id="pend_1", card_id="pendant_of_the_queen_lv0",
        owner_id="inv1", controller_id="inv1",
    )
    inst.uses = {"chargess": 3}  # 生产数据的双 s 键
    state.cards_in_play["pend_1"] = inst
    inv.play_area.append("pend_1")

    impl = PendantOfTheQueen("pend_1")
    impl.register(bus, "pend_1")
    return state, bus, inv, inst, impl


class TestPendantOfTheQueen:
    def test_move_mode(self, setup):
        """模式move：花1充能+消耗，移动到已揭示地点。"""
        state, bus, inv, inst, impl = setup
        assert impl.activate(state, "inv1", mode="move",
                             location_id="loc_b") is True
        assert inv.location_id == "loc_b"
        assert inst.uses["chargess"] == 2
        assert inst.exhausted is True

    def test_discover_mode(self, setup):
        """模式discover：发现该地点1个线索（远程）。"""
        state, bus, inv, inst, impl = setup
        loc_b = state.locations["loc_b"]
        assert impl.activate(state, "inv1", mode="discover",
                             location_id="loc_b") is True
        assert loc_b.clues == 1
        assert inv.clues == 1
        assert inv.location_id == "loc_a"  # 人没动

    def test_evade_mode(self, setup):
        """模式evade：自动躲避该地点一名敌人（横置+脱离交战）。"""
        state, bus, inv, inst, impl = setup
        inv.location_id = "loc_b"
        inv.threat_area.append("e1")
        state.locations["loc_b"].enemies.remove("e1")

        assert impl.activate(state, "inv1", mode="evade",
                             location_id="loc_b") is True
        enemy = state.get_card_instance("e1")
        assert enemy.exhausted is True
        assert "e1" not in inv.threat_area
        assert "e1" in state.locations["loc_b"].enemies

    def test_no_charges_sets_aside_and_recycles_segments(self, setup):
        """充能耗尽：本卡放在一边（场外），3张一瓣缟玛瑙混洗入牌堆。"""
        state, bus, inv, inst, impl = setup
        inst.uses = {"chargess": 1}

        assert impl.activate(state, "inv1", mode="move",
                             location_id="loc_b") is True
        assert "pend_1" not in inv.play_area
        assert "pend_1" not in state.cards_in_play
        assert "pendant_of_the_queen_lv0" in state.scenario.vars["set_aside"]
        assert inv.deck.count("segment_of_onyx_lv1") == 3

    def test_unrevealed_location_rejected(self, setup):
        """未揭示地点不可选。"""
        state, bus, inv, inst, impl = setup
        state.locations["loc_b"].revealed = False
        assert impl.activate(state, "inv1", mode="move",
                             location_id="loc_b") is False
        assert inst.uses["chargess"] == 3
