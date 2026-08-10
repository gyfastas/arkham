"""Tests for Feed the Mind (Level 3)."""

import pytest
from backend.cards.seeker.feed_the_mind_lv3 import FeedTheMind
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

    inv_data = make_investigator_data(intellect=4)
    state.card_database[inv_data.id] = inv_data
    loc_data = make_location_data()
    state.card_database[loc_data.id] = loc_data

    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data,
        location_id="test_location",
        deck=["d1", "d2", "d3", "d4", "d5"],
    )
    state.investigators["inv1"] = inv
    state.locations["test_location"] = LocationState(
        location_id="test_location", card_data=loc_data,
    )

    inst = CardInstance(
        instance_id="ftm_1", card_id="feed_the_mind_lv3",
        owner_id="inv1", controller_id="inv1",
    )
    inst.uses = {"secretss": 3}  # 生产数据的双 s 键
    state.cards_in_play["ftm_1"] = inst
    inv.play_area.append("ftm_1")

    impl = FeedTheMind("ftm_1")
    impl.register(bus, "ftm_1")
    impl.bind_chaos_bag(bag)
    return state, bus, bag, inv, inst, impl


class TestFeedTheMind:
    def test_draw_per_margin(self, setup):
        """智力4 对难度0（0标记）：超4点抽4张，消耗+扣秘密。"""
        state, bus, bag, inv, inst, impl = setup
        bag.tokens = [ChaosTokenType.ZERO]

        assert impl.activate(state, "inv1") is True
        assert len(inv.hand) == 4
        assert len(inv.deck) == 1
        assert inst.uses["secretss"] == 2
        assert inst.exhausted is True

    def test_horror_per_excess_card(self, setup):
        """抽牌后手牌超上限：每张受1点恐惧。"""
        state, bus, bag, inv, inst, impl = setup
        bag.tokens = [ChaosTokenType.ZERO]
        inv.hand = ["h"] * 6  # 抽4张后 10 > 8 → 2点恐惧

        impl.activate(state, "inv1")
        assert len(inv.hand) == 10
        assert inv.horror == 2

    def test_failure_no_draw_but_costs_paid(self, setup):
        """自动失败：不抽牌，但秘密与消耗已支付。"""
        state, bus, bag, inv, inst, impl = setup
        bag.tokens = [ChaosTokenType.AUTO_FAIL]

        assert impl.activate(state, "inv1") is True
        assert len(inv.hand) == 0
        assert inst.uses["secretss"] == 2
        assert inst.exhausted is True
