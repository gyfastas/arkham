"""Tests for "You owe me one!" (Level 0)."""

import pytest

from backend.cards.neutral.emergency_cache_lv0 import EmergencyCache
from backend.cards.rogue.you_owe_me_one_lv0 import YouOweMeOne
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import CardType, GameEvent
from backend.models.state import GameState, InvestigatorState, ScenarioState
from backend.tests.conftest import (
    make_asset_data,
    make_event_data,
    make_investigator_data,
    make_skill_data,
)


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()

    inv_data = make_investigator_data()
    state.card_database[inv_data.id] = inv_data

    state.card_database["you_owe_me_one_lv0"] = make_event_data(
        id="you_owe_me_one_lv0", name='"You owe me one!"')
    state.card_database["test_asset"] = make_asset_data(
        id="test_asset", cost=2)
    state.card_database["expensive_asset"] = make_asset_data(
        id="expensive_asset", cost=5)
    state.card_database["test_skill"] = make_skill_data(id="test_skill")
    weakness = make_asset_data(id="test_weakness", cost=0)
    weakness.subtype = "weakness"
    state.card_database["test_weakness"] = weakness

    inv1 = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1")
    inv1.resources = 3
    inv1.deck = ["deck_card_1"]
    state.investigators["inv1"] = inv1

    inv2 = InvestigatorState(
        investigator_id="inv2", card_data=inv_data, location_id="loc1")
    inv2.deck = ["deck_card_2"]
    state.investigators["inv2"] = inv2

    impl = YouOweMeOne("yomo_impl")
    impl.register(bus, "yomo_impl")

    return state, bus, inv1, inv2


def _play(bus, state, extra=None):
    ctx = EventContext(
        game_state=state,
        event=GameEvent.CARD_PLAYED,
        investigator_id="inv1",
        extra={"card_id": "you_owe_me_one_lv0", **(extra or {})},
    )
    bus.emit(ctx)
    return ctx


class TestYouOweMeOne:
    def test_play_asset_under_your_control_and_both_draw(self, setup):
        """Auto-plays an affordable asset from the other investigator's hand:
        you pay, you control it, they own it, both draw 1."""
        state, bus, inv1, inv2 = setup
        inv2.hand = ["test_asset"]

        ctx = _play(bus, state)

        assert ctx.extra["you_owe_me_one_played"] == "test_asset"
        assert inv1.resources == 1  # paid the asset's cost (3 - 2)
        assert "test_asset" not in inv2.hand
        # In your play area, under your control, owned by the other investigator
        assert len(inv1.play_area) == 1
        inst = state.get_card_instance(inv1.play_area[0])
        assert inst.card_id == "test_asset"
        assert inst.controller_id == "inv1"
        assert inst.owner_id == "inv2"
        # Both drew 1 card
        assert inv1.hand == ["deck_card_1"]
        assert inv2.hand == ["deck_card_2"]
        assert inv1.deck == [] and inv2.deck == []

    def test_explicit_choice_of_card_and_target(self, setup):
        """Session may pass target_investigator + play_card_id to choose."""
        state, bus, inv1, inv2 = setup
        inv2.hand = ["test_asset", "expensive_asset"]
        inv1.resources = 6

        ctx = _play(bus, state, extra={
            "target_investigator": "inv2",
            "play_card_id": "expensive_asset",
        })

        assert ctx.extra["you_owe_me_one_played"] == "expensive_asset"
        assert inv1.resources == 1
        assert inv2.hand == ["test_asset", "deck_card_2"]  # kept card + draw
        inst = state.get_card_instance(inv1.play_area[0])
        assert inst.card_id == "expensive_asset"

    def test_looked_hand_exposed_in_extra(self, setup):
        """The looked-at hand is reported for the session layer to show."""
        state, bus, inv1, inv2 = setup
        inv2.hand = ["test_weakness"]

        ctx = _play(bus, state)

        assert ctx.extra["you_owe_me_one_looked"] == ["test_weakness"]

    def test_weakness_and_skill_not_playable(self, setup):
        """Only weakness/skill cards available: effect fizzles, nobody draws."""
        state, bus, inv1, inv2 = setup
        inv2.hand = ["test_weakness", "test_skill"]

        ctx = _play(bus, state)

        assert "you_owe_me_one_played" not in ctx.extra
        assert inv2.hand == ["test_weakness", "test_skill"]
        assert inv1.hand == [] and inv2.deck == ["deck_card_2"]

    def test_unaffordable_card_fizzles(self, setup):
        """Cannot pay the chosen card's cost: nothing happens."""
        state, bus, inv1, inv2 = setup
        inv2.hand = ["expensive_asset"]  # cost 5 > 3 resources

        ctx = _play(bus, state)

        assert "you_owe_me_one_played" not in ctx.extra
        assert inv1.resources == 3
        assert inv2.hand == ["expensive_asset"]
        assert inv1.deck == ["deck_card_1"]  # no draws

    def test_event_played_from_other_hand(self, setup):
        """An event in the other investigator's hand resolves under your
        control (nested CARD_PLAYED) and goes to its owner's discard."""
        state, bus, inv1, inv2 = setup
        state.card_database["emergency_cache_lv0"] = make_event_data(
            id="emergency_cache_lv0", name="Emergency Cache")
        inv2.hand = ["emergency_cache_lv0"]
        # Simulate the registry-activated temp implementation for the event
        EmergencyCache("ec_impl").register(bus, "ec_impl")

        ctx = _play(bus, state)

        assert ctx.extra["you_owe_me_one_played"] == "emergency_cache_lv0"
        # Emergency Cache resolved under your control: you gained 3 resources
        assert inv1.resources == 6  # 3 - 0 cost + 3 from cache
        # Event goes to its owner's discard
        assert inv2.discard == ["emergency_cache_lv0"]
        assert inv1.hand == ["deck_card_1"]
        assert inv2.hand == ["deck_card_2"]

    def test_solo_game_fizzles(self, setup):
        """No other investigator: nothing happens."""
        state, bus, inv1, inv2 = setup
        del state.investigators["inv2"]

        ctx = _play(bus, state)

        assert "you_owe_me_one_played" not in ctx.extra
        assert inv1.resources == 3
        assert inv1.deck == ["deck_card_1"]
