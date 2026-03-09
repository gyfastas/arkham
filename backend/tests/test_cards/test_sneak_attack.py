"""Tests for Sneak Attack (Level 0)."""

import pytest
from backend.cards.rogue.sneak_attack_lv0 import SneakAttack
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent
from backend.models.state import GameState, InvestigatorState, ScenarioState, CardInstance
from backend.tests.conftest import make_investigator_data, make_event_data, make_enemy_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()

    inv_data = make_investigator_data()
    state.card_database[inv_data.id] = inv_data

    card_data = make_event_data(id="sneak_attack_lv0")
    state.card_database["sneak_attack_lv0"] = card_data

    enemy_data = make_enemy_data(id="ghoul")
    state.card_database["ghoul"] = enemy_data

    inv = InvestigatorState(
        investigator_id="inv1",
        card_data=inv_data,
        location_id="loc1",
    )
    state.investigators["inv1"] = inv

    enemy_inst = CardInstance(
        instance_id="ghoul_1",
        card_id="ghoul",
        owner_id="scenario",
        controller_id="scenario",
    )
    enemy_inst.damage = 0
    state.cards_in_play["ghoul_1"] = enemy_inst

    impl = SneakAttack("sneak_inst")
    impl.register(bus, "sneak_inst")
    return state, bus, inv, impl


class TestSneakAttack:
    def test_deal_damage_to_exhausted_enemy(self, setup):
        """Sneak Attack deals 2 damage to target enemy."""
        state, bus, inv, impl = setup

        ctx = EventContext(
            game_state=state,
            event=GameEvent.CARD_PLAYED,
            investigator_id="inv1",
            extra={"card_id": "sneak_attack_lv0", "target_enemy_id": "ghoul_1"},
        )
        bus.emit(ctx)

        assert state.cards_in_play["ghoul_1"].damage == 2

    def test_no_damage_without_target(self, setup):
        """No damage if no target enemy specified."""
        state, bus, inv, impl = setup

        ctx = EventContext(
            game_state=state,
            event=GameEvent.CARD_PLAYED,
            investigator_id="inv1",
            extra={"card_id": "sneak_attack_lv0"},
        )
        bus.emit(ctx)

        assert state.cards_in_play["ghoul_1"].damage == 0
