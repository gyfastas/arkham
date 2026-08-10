"""Tests for Swift Reload (Level 2)."""

import pytest

from backend.cards.rogue.swift_reload_lv2 import SwiftReload
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, ScenarioState,
)
from backend.tests.conftest import make_asset_data, make_investigator_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()
    inv_data = make_investigator_data()
    state.card_database[inv_data.id] = inv_data
    gun_data = make_asset_data(
        id="test_gun", uses={"ammo": 4}, traits=["item", "weapon", "firearm"])
    state.card_database["test_gun"] = gun_data
    tome_data = make_asset_data(
        id="test_tome", uses={"secrets": 3}, traits=["item", "tome"])
    state.card_database["test_tome"] = tome_data
    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1")
    state.investigators["inv1"] = inv
    state.cards_in_play["gun_1"] = CardInstance(
        instance_id="gun_1", card_id="test_gun",
        owner_id="inv1", controller_id="inv1", uses={"ammo": 1})
    state.cards_in_play["tome_1"] = CardInstance(
        instance_id="tome_1", card_id="test_tome",
        owner_id="inv1", controller_id="inv1", uses={"secrets": 1})
    inv.play_area.extend(["gun_1", "tome_1"])
    impl = SwiftReload("reload_inst")
    impl.register(bus, "reload_inst")
    return state, bus, inv


def _play(bus, state, **extra):
    ctx = EventContext(
        game_state=state,
        event=GameEvent.CARD_PLAYED,
        investigator_id="inv1",
        extra={"card_id": "swift_reload_lv2", **extra},
    )
    bus.emit(ctx)
    return ctx


class TestSwiftReload:
    def test_refills_firearm_to_full(self, setup):
        state, bus, inv = setup
        ctx = _play(bus, state)
        assert ctx.extra["swift_reload_target"] == "gun_1"
        assert ctx.extra["swift_reload_added"] == 3
        assert state.get_card_instance("gun_1").uses["ammo"] == 4

    def test_non_firearm_not_reloaded(self, setup):
        """Tome (secrets, not firearm) is never a valid target."""
        state, bus, inv = setup
        ctx = _play(bus, state, target_instance_id="tome_1")
        assert "swift_reload_target" not in ctx.extra
        assert state.get_card_instance("tome_1").uses["secrets"] == 1

    def test_full_firearm_not_reloaded(self, setup):
        state, bus, inv = setup
        state.get_card_instance("gun_1").uses["ammo"] = 4
        ctx = _play(bus, state)
        assert "swift_reload_target" not in ctx.extra

    def test_explicit_target(self, setup):
        state, bus, inv = setup
        state.cards_in_play["gun_2"] = CardInstance(
            instance_id="gun_2", card_id="test_gun",
            owner_id="inv1", controller_id="inv1", uses={"ammo": 2})
        inv.play_area.append("gun_2")
        ctx = _play(bus, state, target_instance_id="gun_2")
        assert ctx.extra["swift_reload_target"] == "gun_2"
        assert state.get_card_instance("gun_2").uses["ammo"] == 4
        assert state.get_card_instance("gun_1").uses["ammo"] == 1
