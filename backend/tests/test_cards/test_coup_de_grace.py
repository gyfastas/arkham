"""Tests for Coup de Grâce (Level 0)."""

import importlib

import pytest
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, LocationState, ScenarioState,
)
from backend.tests.conftest import (
    make_enemy_data, make_investigator_data, make_location_data,
)

_mod = importlib.import_module("backend.cards.rogue.coup_de_grâce_lv0")
CoupDeGrace = _mod.CoupDeGrace


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
    inv.actions_remaining = 3
    inv.deck = ["card_a"]
    state.investigators["inv1"] = inv

    state.card_database["test_enemy"] = make_enemy_data(health=1)
    state.card_database["big_enemy"] = make_enemy_data(id="big_enemy", health=5)

    impl = CoupDeGrace("cdg_inst")
    impl.register(bus, "cdg_inst")
    return state, bus, inv, impl


def _add_enemy(state, inv, card_id, instance_id, engaged=True):
    state.cards_in_play[instance_id] = CardInstance(
        instance_id=instance_id, card_id=card_id,
        owner_id="scenario", controller_id="scenario",
    )
    if engaged:
        inv.threat_area.append(instance_id)
    else:
        state.locations["loc1"].enemies.append(instance_id)


class TestCoupDeGrace:
    def test_damage_defeats_draws_card_ends_turn(self, setup):
        """造成1伤害；击败1血敌人 → 抽1张牌；结束回合（行动归0）。"""
        state, bus, inv, impl = setup
        _add_enemy(state, inv, "test_enemy", "enemy_1")
        ctx = EventContext(
            game_state=state, event=GameEvent.CARD_PLAYED,
            investigator_id="inv1", extra={"card_id": "coup_de_grâce_lv0"},
        )
        bus.emit(ctx)
        assert state.get_card_instance("enemy_1") is None  # 被击败离场
        assert "enemy_1" not in inv.threat_area
        assert "test_enemy" in state.scenario.encounter_discard
        assert inv.hand == ["card_a"]  # 击败抽1
        assert inv.actions_remaining == 0  # 结束回合
        assert ctx.extra["coup_de_grace_drew"] is True

    def test_no_draw_when_not_defeated(self, setup):
        """未击败：不抽牌，仍结束回合。"""
        state, bus, inv, impl = setup
        _add_enemy(state, inv, "big_enemy", "enemy_1")
        ctx = EventContext(
            game_state=state, event=GameEvent.CARD_PLAYED,
            investigator_id="inv1", extra={"card_id": "coup_de_grâce_lv0"},
        )
        bus.emit(ctx)
        enemy = state.get_card_instance("enemy_1")
        assert enemy.damage == 1
        assert inv.hand == []
        assert inv.actions_remaining == 0
        assert "coup_de_grace_drew" not in ctx.extra

    def test_targets_unengaged_enemy_at_location(self, setup):
        """无交战敌人时选地点上的未交战敌人。"""
        state, bus, inv, impl = setup
        _add_enemy(state, inv, "big_enemy", "enemy_1", engaged=False)
        ctx = EventContext(
            game_state=state, event=GameEvent.CARD_PLAYED,
            investigator_id="inv1", extra={"card_id": "coup_de_grâce_lv0"},
        )
        bus.emit(ctx)
        assert state.get_card_instance("enemy_1").damage == 1
