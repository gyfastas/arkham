"""Tests for Sneak Attack (Level 2)."""

import pytest
from backend.cards.rogue.sneak_attack_lv2 import SneakAttackLv2
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, LocationState, ScenarioState,
)
from backend.tests.conftest import (
    make_enemy_data, make_event_data, make_investigator_data,
    make_location_data,
)


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()

    inv_data = make_investigator_data()
    state.card_database[inv_data.id] = inv_data
    state.card_database["sneak_attack_lv2"] = make_event_data(
        id="sneak_attack_lv2", cost=2,
    )
    # 3 health: survives 2 damage
    state.card_database["ghoul"] = make_enemy_data(id="ghoul", health=3)
    # 2 health: defeated by 2 damage
    state.card_database["rat"] = make_enemy_data(id="rat", health=2)

    loc_data = make_location_data(id="loc1")
    state.card_database["loc1"] = loc_data
    loc = LocationState(location_id="loc1", card_data=loc_data, revealed=True)
    state.locations["loc1"] = loc

    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1",
    )
    state.investigators["inv1"] = inv

    # Unengaged enemy at the location
    state.cards_in_play["ghoul_1"] = CardInstance(
        instance_id="ghoul_1", card_id="ghoul",
        owner_id="scenario", controller_id="scenario",
    )
    loc.enemies.append("ghoul_1")
    # Enemy engaged WITH YOU (not a valid target)
    state.cards_in_play["ghoul_2"] = CardInstance(
        instance_id="ghoul_2", card_id="ghoul",
        owner_id="scenario", controller_id="scenario",
    )
    inv.threat_area.append("ghoul_2")

    impl = SneakAttackLv2("sa2_inst")
    impl.register(bus, "sa2_inst")
    return state, bus, inv, impl


def _play(bus, state, **extra):
    ctx = EventContext(
        game_state=state, event=GameEvent.CARD_PLAYED,
        investigator_id="inv1",
        extra={"card_id": "sneak_attack_lv2", **extra},
    )
    bus.emit(ctx)
    return ctx


class TestSneakAttackLv2:
    def test_card_id(self):
        assert SneakAttackLv2.card_id == "sneak_attack_lv2"

    def test_default_targets_unengaged_enemy(self, setup):
        """Deal 2 damage to an enemy not engaged with you at your location."""
        state, bus, inv, impl = setup
        ctx = _play(bus, state)

        assert state.cards_in_play["ghoul_1"].damage == 2
        assert ctx.extra["sneak_attack_lv2_target"] == "ghoul_1"

    def test_engaged_with_you_not_targetable(self, setup):
        """An enemy engaged with you is not a valid target."""
        state, bus, inv, impl = setup
        _play(bus, state, target_enemy_id="ghoul_2")
        assert state.cards_in_play["ghoul_2"].damage == 0

    def test_enemy_engaged_with_other_investigator_valid(self, setup):
        """An enemy engaged with ANOTHER investigator at your location is valid."""
        state, bus, inv, impl = setup
        other_data = make_investigator_data(id="other_inv")
        state.card_database["other_inv"] = other_data
        other = InvestigatorState(
            investigator_id="other_inv", card_data=other_data,
            location_id="loc1",
        )
        state.investigators["other_inv"] = other
        state.cards_in_play["ghoul_3"] = CardInstance(
            instance_id="ghoul_3", card_id="ghoul",
            owner_id="scenario", controller_id="scenario",
        )
        other.threat_area.append("ghoul_3")

        _play(bus, state, target_enemy_id="ghoul_3")
        assert state.cards_in_play["ghoul_3"].damage == 2

    def test_enemy_elsewhere_not_targetable(self, setup):
        state, bus, inv, impl = setup
        loc2_data = make_location_data(id="loc2")
        state.card_database["loc2"] = loc2_data
        loc2 = LocationState(location_id="loc2", card_data=loc2_data, revealed=True)
        state.locations["loc2"] = loc2
        state.cards_in_play["ghoul_4"] = CardInstance(
            instance_id="ghoul_4", card_id="ghoul",
            owner_id="scenario", controller_id="scenario",
        )
        loc2.enemies.append("ghoul_4")

        _play(bus, state, target_enemy_id="ghoul_4")
        assert state.cards_in_play["ghoul_4"].damage == 0

    def test_lethal_damage_defeats_enemy(self, setup):
        """2 damage vs 2 health: enemy is defeated via the defeat flow."""
        state, bus, inv, impl = setup
        defeated = []
        bus.register(
            GameEvent.ENEMY_DEFEATED,
            lambda ctx: defeated.append((ctx.target, ctx.investigator_id,
                                         ctx.extra.get("card_id"))),
        )
        state.cards_in_play["rat_1"] = CardInstance(
            instance_id="rat_1", card_id="rat",
            owner_id="scenario", controller_id="scenario",
        )
        state.locations["loc1"].enemies.append("rat_1")

        ctx = _play(bus, state, target_enemy_id="rat_1")

        assert "rat_1" not in state.cards_in_play
        assert "rat_1" not in state.locations["loc1"].enemies
        assert "rat" in state.scenario.encounter_discard
        assert defeated == [("rat_1", "inv1", "rat")]
        assert ctx.extra["sneak_attack_lv2_defeated"] == "rat_1"
