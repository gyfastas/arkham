"""Tests for Untimely Transaction (Level 1)."""

import pytest

from backend.cards.rogue.untimely_transaction_lv1 import UntimelyTransaction
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent
from backend.models.state import GameState, InvestigatorState, ScenarioState
from backend.tests.conftest import make_asset_data, make_investigator_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()
    inv_data = make_investigator_data()
    state.card_database[inv_data.id] = inv_data
    ally_data = make_investigator_data(id="ally_data")
    state.card_database["ally_data"] = ally_data
    item = make_asset_data(id="item_gun", cost=3, traits=["item", "weapon"])
    state.card_database["item_gun"] = item
    not_item = make_asset_data(id="tome", cost=2, traits=["tome"])
    state.card_database["tome"] = not_item

    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1",
        hand=["item_gun"], deck=["next_card"],
    )
    inv.resources = 1
    state.investigators["inv1"] = inv
    ally = InvestigatorState(
        investigator_id="inv2", card_data=ally_data, location_id="loc1")
    ally.resources = 5
    state.investigators["inv2"] = ally

    impl = UntimelyTransaction("ut_inst")
    impl.register(bus, "ut_inst")
    return state, bus, inv, ally


def _play(bus, state, **extra):
    ctx = EventContext(
        game_state=state,
        event=GameEvent.CARD_PLAYED,
        investigator_id="inv1",
        extra={"card_id": "untimely_transaction_lv1", **extra},
    )
    bus.emit(ctx)
    return ctx


class TestUntimelyTransaction:
    def test_ally_plays_item_and_owner_compensated(self, setup):
        state, bus, inv, ally = setup
        ctx = _play(bus, state)
        assert ctx.extra["untimely_transaction_item"] == "item_gun"
        assert ctx.extra["untimely_transaction_buyer"] == "inv2"
        # 对方支付打印费用，道具进入其装备区
        assert ally.resources == 2
        new_id = next(i for i in ally.play_area)
        assert state.get_card_instance(new_id).card_id == "item_gun"
        # 你失去该手牌，抽1张牌，获得等于打印费用的资源
        assert inv.hand == ["next_card"]
        assert inv.resources == 1 + 3
        assert ctx.extra["untimely_transaction_refund"] == 3

    def test_no_other_investigator_no_effect(self, setup):
        state, bus, inv, ally = setup
        ally.location_id = "elsewhere"
        ctx = _play(bus, state)
        assert "untimely_transaction_item" not in ctx.extra
        assert inv.hand == ["item_gun"]
        assert inv.resources == 1

    def test_ally_cannot_afford_no_effect(self, setup):
        state, bus, inv, ally = setup
        ally.resources = 2  # 打印费用3
        ctx = _play(bus, state)
        assert "untimely_transaction_item" not in ctx.extra
        assert inv.hand == ["item_gun"]

    def test_non_item_not_revealed(self, setup):
        state, bus, inv, ally = setup
        inv.hand = ["tome"]
        ctx = _play(bus, state)
        assert "untimely_transaction_item" not in ctx.extra
        assert inv.hand == ["tome"]

    def test_explicit_item_and_target(self, setup):
        state, bus, inv, ally = setup
        inv.hand = ["tome", "item_gun"]
        ctx = _play(bus, state, item_card_id="item_gun",
                    target_investigator_id="inv2")
        assert ctx.extra["untimely_transaction_item"] == "item_gun"
        assert ally.resources == 2
