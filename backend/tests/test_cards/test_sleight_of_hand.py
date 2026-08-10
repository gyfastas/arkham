"""Tests for Sleight of Hand (Level 0)."""

import pytest
from backend.cards.rogue.sleight_of_hand_lv0 import SleightOfHand
from backend.engine.event_bus import EventBus, EventContext
from backend.engine.slots import SlotManager
from backend.models.enums import GameEvent, SlotType
from backend.models.state import (
    GameState, InvestigatorState, ScenarioState,
)
from backend.tests.conftest import (
    make_asset_data, make_event_data, make_investigator_data,
)


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()

    inv_data = make_investigator_data()
    state.card_database[inv_data.id] = inv_data
    state.card_database["sleight_of_hand_lv0"] = make_event_data(
        id="sleight_of_hand_lv0", cost=1, fast=True,
    )
    state.card_database["lockpicks_lv1"] = make_asset_data(
        id="lockpicks_lv1", cost=3, slots=[SlotType.HAND],
        uses={"supply": 3}, traits=["item", "tool", "illicit"],
    )
    state.card_database["beat_cop_lv0"] = make_asset_data(
        id="beat_cop_lv0", cost=4, slots=[SlotType.ALLY],
        health=2, sanity=2, traits=["ally", "police"],
    )

    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1",
        hand=["lockpicks_lv1", "beat_cop_lv0"],
    )
    state.investigators["inv1"] = inv
    state.slot_managers = {"inv1": SlotManager()}

    impl = SleightOfHand("soh_inst")
    impl.register(bus, "soh_inst")
    return state, bus, inv, impl


def _play(bus, state, **extra):
    ctx = EventContext(
        game_state=state, event=GameEvent.CARD_PLAYED,
        investigator_id="inv1",
        extra={"card_id": "sleight_of_hand_lv0", **extra},
    )
    bus.emit(ctx)
    return ctx


def _turn_ends(bus, state):
    ctx = EventContext(
        game_state=state, event=GameEvent.INVESTIGATOR_TURN_ENDS,
        investigator_id="inv1",
    )
    bus.emit(ctx)
    return ctx


class TestSleightOfHand:
    def test_card_id(self):
        assert SleightOfHand.card_id == "sleight_of_hand_lv0"

    def test_puts_first_item_into_play(self, setup):
        """Put an Item asset from your hand into play (free)."""
        state, bus, inv, impl = setup
        ctx = _play(bus, state)

        iid = ctx.extra["sleight_of_hand_instance"]
        inst = state.cards_in_play[iid]
        assert inst.card_id == "lockpicks_lv1"  # first Item in hand
        assert iid in inv.play_area
        assert inst.uses == {"supply": 3}
        assert "lockpicks_lv1" not in inv.hand
        # Slot occupied
        mgr = state.slot_managers["inv1"]
        assert iid in mgr.slots[SlotType.HAND]

    def test_explicit_item_choice(self, setup):
        state, bus, inv, impl = setup
        ctx = _play(bus, state, asset_card_id="lockpicks_lv1")
        inst = state.cards_in_play[ctx.extra["sleight_of_hand_instance"]]
        assert inst.card_id == "lockpicks_lv1"

    def test_non_item_not_selected(self, setup):
        """Beat Cop (ally, not item) is not a valid target."""
        state, bus, inv, impl = setup
        ctx = _play(bus, state, asset_card_id="beat_cop_lv0")
        assert "sleight_of_hand_instance" not in ctx.extra
        assert "beat_cop_lv0" in inv.hand

    def test_returns_to_hand_at_turn_end(self, setup):
        """At the end of your turn, return the asset to your hand."""
        state, bus, inv, impl = setup
        ctx = _play(bus, state)
        iid = ctx.extra["sleight_of_hand_instance"]

        end_ctx = _turn_ends(bus, state)
        assert iid not in inv.play_area
        assert iid not in state.cards_in_play
        assert "lockpicks_lv1" in inv.hand
        assert end_ctx.extra["sleight_of_hand_returned"] == "lockpicks_lv1"
        # Slot freed
        mgr = state.slot_managers["inv1"]
        assert iid not in mgr.slots[SlotType.HAND]

    def test_not_returned_if_left_play(self, setup):
        """If the asset is no longer in play at turn end, nothing happens."""
        state, bus, inv, impl = setup
        ctx = _play(bus, state)
        iid = ctx.extra["sleight_of_hand_instance"]

        # Simulate the asset being discarded mid-turn
        inv.play_area.remove(iid)
        state.cards_in_play.pop(iid)
        bus.emit(EventContext(
            game_state=state, event=GameEvent.CARD_LEAVES_PLAY,
            investigator_id="inv1", target=iid,
            extra={"card_id": "lockpicks_lv1"},
        ))
        inv.discard.append("lockpicks_lv1")

        _turn_ends(bus, state)
        assert "lockpicks_lv1" not in inv.hand
        assert "lockpicks_lv1" in inv.discard

    def test_no_item_in_hand_noop(self, setup):
        state, bus, inv, impl = setup
        inv.hand = ["beat_cop_lv0"]
        ctx = _play(bus, state)
        assert "sleight_of_hand_instance" not in ctx.extra
