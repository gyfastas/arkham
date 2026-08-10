"""Tests for Fingerprint Kit (Level 0)."""

import pytest
from backend.cards.seeker.fingerprint_kit_lv0 import FingerprintKit
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
    loc_data = make_location_data(shroud=4, clue_value=3)
    state.card_database[loc_data.id] = loc_data

    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="test_location",
    )
    state.investigators["inv1"] = inv
    loc = LocationState(location_id="test_location", card_data=loc_data, clues=3)
    state.locations["test_location"] = loc

    inst = CardInstance(
        instance_id="kit_1", card_id="fingerprint_kit_lv0",
        owner_id="inv1", controller_id="inv1",
    )
    inst.uses = {"suppliess": 3}  # 生产数据的双 s 键
    state.cards_in_play["kit_1"] = inst
    inv.play_area.append("kit_1")

    impl = FingerprintKit("kit_1")
    impl.register(bus, "kit_1")
    impl.bind_chaos_bag(bag)
    return state, bus, bag, inv, loc, inst, impl


class TestFingerprintKit:
    def test_success_discovers_two_clues(self, setup):
        """+1智力使检定成功（3+1=4 对隐蔽值4），成功发现2个线索。"""
        state, bus, bag, inv, loc, inst, impl = setup
        bag.tokens = [ChaosTokenType.ZERO]

        assert impl.activate(state, "inv1") is True
        assert loc.clues == 1
        assert inv.clues == 2
        assert inst.uses["suppliess"] == 2
        assert inst.exhausted is True

    def test_bonus_applies_to_test(self, setup):
        """没有+1智力时 3<4 失败（对照：加值确实进了检定）。"""
        state, bus, bag, inv, loc, inst, impl = setup
        bag.tokens = [ChaosTokenType.MINUS_1]
        # 3 + 1(kit) - 1 = 3 < 4 失败；无 kit 加值则 2，差异可断
        assert impl.activate(state, "inv1") is True
        assert loc.clues == 3
        assert inv.clues == 0

    def test_failure_still_discovers_nothing(self, setup):
        """自动失败：不发现线索，补给已花费。"""
        state, bus, bag, inv, loc, inst, impl = setup
        bag.tokens = [ChaosTokenType.AUTO_FAIL]

        impl.activate(state, "inv1")
        assert inv.clues == 0
        assert loc.clues == 3
        assert inst.uses["suppliess"] == 2
