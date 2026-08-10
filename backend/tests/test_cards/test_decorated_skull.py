"""Tests for Decorated Skull (Level 0)."""

import pytest
from backend.cards.rogue.decorated_skull_lv0 import DecoratedSkull
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, LocationState, ScenarioState,
)
from backend.tests.conftest import (
    make_asset_data, make_enemy_data, make_investigator_data,
    make_location_data,
)


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()
    inv_data = make_investigator_data()
    state.card_database[inv_data.id] = inv_data
    loc_data = make_location_data(id="loc1")
    state.card_database["loc1"] = loc_data
    state.locations["loc1"] = LocationState(
        location_id="loc1", card_data=loc_data, revealed=True,
    )
    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1",
    )
    inv.resources = 3
    inv.deck = ["card_a", "card_b"]
    state.investigators["inv1"] = inv

    enemy_data = make_enemy_data()
    state.card_database["test_enemy"] = enemy_data
    state.cards_in_play["enemy_1"] = CardInstance(
        instance_id="enemy_1", card_id="test_enemy",
        owner_id="scenario", controller_id="scenario",
    )
    state.locations["loc1"].enemies.append("enemy_1")

    ally_data = make_asset_data(id="ally_x", name="Ally", traits=["ally"], health=2)
    state.card_database["ally_x"] = ally_data

    impl = DecoratedSkull("skull_inst")
    impl.register(bus, "skull_inst")
    ci = CardInstance(
        instance_id="skull_inst", card_id="decorated_skull_lv0",
        owner_id="inv1", controller_id="inv1",
        uses={"chargess": 0},  # 数据笔误键名，实现应兼容
    )
    state.cards_in_play["skull_inst"] = ci
    inv.play_area.append("skull_inst")
    return state, bus, inv, impl, ci


class TestDecoratedSkull:
    def test_enemy_defeated_at_location_adds_charge(self, setup):
        """你所在地点的敌人被击败：+1充能（chargess 键规整为 charges）。"""
        state, bus, inv, impl, ci = setup
        bus.emit(EventContext(
            game_state=state, event=GameEvent.ENEMY_DEFEATED,
            target="enemy_1", investigator_id="inv1",
        ))
        assert ci.uses.get("charges") == 1
        assert "chargess" not in ci.uses

    def test_enemy_elsewhere_no_charge(self, setup):
        """其他地点的敌人被击败：不加充能。"""
        state, bus, inv, impl, ci = setup
        loc2_data = make_location_data(id="loc2")
        state.card_database["loc2"] = loc2_data
        state.locations["loc2"] = LocationState(
            location_id="loc2", card_data=loc2_data, revealed=True,
        )
        state.locations["loc1"].enemies.remove("enemy_1")
        state.locations["loc2"].enemies.append("enemy_1")
        bus.emit(EventContext(
            game_state=state, event=GameEvent.ENEMY_DEFEATED,
            target="enemy_1", investigator_id="inv1",
        ))
        assert ci.uses.get("chargess", 0) == 0
        assert ci.uses.get("charges", 0) == 0

    def test_ally_defeated_adds_charge(self, setup):
        """你所在地点调查员的盟友支援被击败：+1充能。"""
        state, bus, inv, impl, ci = setup
        ally = CardInstance(
            instance_id="ally_inst", card_id="ally_x",
            owner_id="inv1", controller_id="inv1",
        )
        state.cards_in_play["ally_inst"] = ally
        inv.play_area.append("ally_inst")
        bus.emit(EventContext(
            game_state=state, event=GameEvent.ASSET_DEFEATED,
            target="ally_inst",
        ))
        assert ci.uses.get("charges") == 1

    def test_spend_charge_draws_and_gains_resource(self, setup):
        """[行动]花1充能：抽1张牌并获得1资源。"""
        state, bus, inv, impl, ci = setup
        ci.uses["charges"] = 2
        assert impl.spend_charge(state, "inv1") is True
        assert ci.uses["charges"] == 1
        assert inv.hand == ["card_a"]
        assert inv.resources == 4

    def test_spend_charge_requires_charge(self, setup):
        state, bus, inv, impl, ci = setup
        assert impl.spend_charge(state, "inv1") is False
        assert inv.hand == []
