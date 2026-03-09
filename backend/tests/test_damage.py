"""Tests for DamageEngine."""

import pytest
from backend.engine.damage import DamageEngine
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent, CardType
from backend.models.state import (
    CardData, CardInstance, GameState, InvestigatorState, ScenarioState,
)
from backend.tests.conftest import make_enemy_data, make_investigator_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()

    inv_data = make_investigator_data(health=7, sanity=7)
    state.card_database[inv_data.id] = inv_data

    inv = InvestigatorState(
        investigator_id="inv1",
        card_data=inv_data,
        location_id="loc1",
    )
    state.investigators["inv1"] = inv

    engine = DamageEngine(state, bus)
    return state, bus, engine, inv


class TestDealDamage:
    def test_deal_damage_to_investigator(self, setup):
        state, bus, engine, inv = setup
        engine.deal_damage("inv1", damage=2)
        assert inv.damage == 2

    def test_deal_horror_to_investigator(self, setup):
        state, bus, engine, inv = setup
        engine.deal_damage("inv1", horror=3)
        assert inv.horror == 3

    def test_deal_damage_and_horror(self, setup):
        state, bus, engine, inv = setup
        engine.deal_damage("inv1", damage=1, horror=2)
        assert inv.damage == 1
        assert inv.horror == 2

    def test_investigator_defeated_by_damage(self, setup):
        state, bus, engine, inv = setup
        defeated = []
        bus.register(GameEvent.INVESTIGATOR_DEFEATED, lambda ctx: defeated.append(True))

        engine.deal_damage("inv1", damage=7)
        assert inv.is_defeated
        assert defeated == [True]

    def test_investigator_defeated_by_horror(self, setup):
        state, bus, engine, inv = setup
        defeated = []
        bus.register(GameEvent.INVESTIGATOR_DEFEATED, lambda ctx: defeated.append(True))

        engine.deal_damage("inv1", horror=7)
        assert inv.is_defeated
        assert defeated == [True]


class TestDealDamageToEnemy:
    def test_deal_damage_to_enemy(self, setup):
        state, bus, engine, inv = setup
        enemy_data = make_enemy_data(health=3)
        state.card_database["test_enemy"] = enemy_data

        enemy = CardInstance(
            instance_id="enemy_1", card_id="test_enemy",
            owner_id="scenario", controller_id="scenario",
        )
        state.cards_in_play["enemy_1"] = enemy

        engine.deal_damage_to_enemy("enemy_1", 2)
        assert enemy.damage == 2

    def test_enemy_defeated(self, setup):
        state, bus, engine, inv = setup
        enemy_data = make_enemy_data(health=2)
        state.card_database["test_enemy"] = enemy_data

        enemy = CardInstance(
            instance_id="enemy_1", card_id="test_enemy",
            owner_id="scenario", controller_id="scenario",
        )
        state.cards_in_play["enemy_1"] = enemy
        inv.threat_area.append("enemy_1")

        defeated = []
        bus.register(GameEvent.ENEMY_DEFEATED, lambda ctx: defeated.append(True))

        result = engine.deal_damage_to_enemy("enemy_1", 3)
        assert result  # enemy defeated
        assert defeated == [True]
        assert "enemy_1" not in state.cards_in_play
        assert "enemy_1" not in inv.threat_area


class TestHeal:
    def test_heal_damage(self, setup):
        state, bus, engine, inv = setup
        inv.damage = 3
        engine.heal(investigator_id="inv1", damage=2)
        assert inv.damage == 1

    def test_heal_cannot_go_below_zero(self, setup):
        state, bus, engine, inv = setup
        inv.damage = 1
        engine.heal(investigator_id="inv1", damage=5)
        assert inv.damage == 0
