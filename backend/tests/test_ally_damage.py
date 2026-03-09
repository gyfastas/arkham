"""Tests for ally damage soaking and defeat mechanics."""

import pytest
from backend.engine.damage import DamageEngine
from backend.engine.event_bus import EventBus
from backend.models.enums import CardType, PlayerClass, SlotType
from backend.models.state import (
    CardData, CardInstance, GameState, InvestigatorState,
    LocationState, ScenarioState, SkillValues,
)
from backend.tests.conftest import make_investigator_data, make_asset_data, make_location_data


@pytest.fixture
def setup():
    """Create game state with investigator, ally (Dr. Milan), and location."""
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()

    inv_data = make_investigator_data(health=5, sanity=9)
    state.card_database[inv_data.id] = inv_data

    # Dr. Milan: health=1, sanity=2
    milan_data = make_asset_data(
        id="dr_milan_christopher_lv0",
        name="Dr. Milan Christopher",
        slots=[SlotType.ALLY],
        traits=["ally", "miskatonic"],
        health=1, sanity=2,
    )
    state.card_database["dr_milan_christopher_lv0"] = milan_data

    loc_data = make_location_data()
    state.card_database[loc_data.id] = loc_data

    inv = InvestigatorState(
        investigator_id="inv1",
        card_data=inv_data,
        location_id="test_location",
    )
    state.investigators["inv1"] = inv
    state.player_order = ["inv1"]

    loc = LocationState(location_id="test_location", card_data=loc_data, clues=2)
    state.locations["test_location"] = loc

    # Put Dr. Milan in play
    milan_ci = CardInstance(
        instance_id="inst_milan",
        card_id="dr_milan_christopher_lv0",
        owner_id="inv1",
        controller_id="inv1",
    )
    state.cards_in_play["inst_milan"] = milan_ci
    inv.play_area.append("inst_milan")

    engine = DamageEngine(state, bus)
    return state, bus, engine, inv


class TestAllyDamageSoaking:
    def test_no_assignment_all_to_investigator(self, setup):
        """Without damage assignment, all damage goes to investigator."""
        state, bus, engine, inv = setup
        engine.deal_damage("inv1", damage=2, horror=1)
        assert inv.damage == 2
        assert inv.horror == 1
        # Milan untouched
        milan = state.get_card_instance("inst_milan")
        assert milan.damage == 0
        assert milan.horror == 0

    def test_assign_damage_to_ally(self, setup):
        """Damage can be assigned to ally, reducing investigator damage."""
        state, bus, engine, inv = setup
        engine.deal_damage(
            "inv1", damage=2, horror=0,
            damage_assignment={"inst_milan": 1},
        )
        # 1 damage to Milan (defeats it since HP=1), 1 to investigator
        assert inv.damage == 1
        # Milan is defeated (1 damage = 1 health)
        assert "inst_milan" not in state.cards_in_play

    def test_assign_horror_to_ally(self, setup):
        """Horror can be assigned to ally, reducing investigator horror."""
        state, bus, engine, inv = setup
        engine.deal_damage(
            "inv1", damage=0, horror=2,
            horror_assignment={"inst_milan": 2},
        )
        # Milan soaks all 2 horror (sanity=2), then defeated
        assert inv.horror == 0
        assert "inst_milan" not in state.cards_in_play

    def test_ally_cannot_soak_beyond_health(self, setup):
        """Ally can only soak damage up to its remaining health."""
        state, bus, engine, inv = setup
        # Milan has 1 HP — try to assign 3 damage to Milan
        engine.deal_damage(
            "inv1", damage=3, horror=0,
            damage_assignment={"inst_milan": 3},
        )
        # Milan soaks 1 (its max HP), investigator gets 2
        assert inv.damage == 2
        milan = state.get_card_instance("inst_milan")
        # Milan is defeated and removed from play
        assert "inst_milan" not in state.cards_in_play

    def test_ally_cannot_soak_beyond_sanity(self, setup):
        """Ally can only soak horror up to its remaining sanity."""
        state, bus, engine, inv = setup
        # Milan has 2 SAN — try to assign 4 horror
        engine.deal_damage(
            "inv1", damage=0, horror=4,
            horror_assignment={"inst_milan": 4},
        )
        # Milan soaks 2, investigator gets 2
        assert inv.horror == 2

    def test_ally_defeated_when_health_zero(self, setup):
        """Ally is defeated and removed from play when health reaches 0."""
        state, bus, engine, inv = setup
        engine.deal_damage(
            "inv1", damage=1, horror=0,
            damage_assignment={"inst_milan": 1},
        )
        # Milan had 1 HP, took 1 damage → defeated
        assert "inst_milan" not in state.cards_in_play
        assert "inst_milan" not in inv.play_area
        assert "dr_milan_christopher_lv0" in inv.discard

    def test_ally_defeated_when_sanity_zero(self, setup):
        """Ally is defeated and removed from play when sanity reaches 0."""
        state, bus, engine, inv = setup
        engine.deal_damage(
            "inv1", damage=0, horror=2,
            horror_assignment={"inst_milan": 2},
        )
        # Milan had 2 SAN, took 2 horror → defeated
        assert "inst_milan" not in state.cards_in_play
        assert "inst_milan" not in inv.play_area

    def test_direct_damage_bypasses_ally(self, setup):
        """Direct damage goes straight to investigator, cannot be soaked."""
        state, bus, engine, inv = setup
        engine.deal_damage("inv1", damage=2, horror=1, direct=True)
        assert inv.damage == 2
        assert inv.horror == 1
        milan = state.get_card_instance("inst_milan")
        assert milan.damage == 0

    def test_mixed_damage_and_horror_assignment(self, setup):
        """Both damage and horror can be assigned to allies simultaneously.

        Note: damage is applied first. Milan has 1 HP, so 1 damage defeats it.
        The horror assignment to Milan then fails (Milan already gone).
        """
        state, bus, engine, inv = setup
        engine.deal_damage(
            "inv1", damage=2, horror=3,
            damage_assignment={"inst_milan": 1},
            horror_assignment={"inst_milan": 1},
        )
        # Milan soaks 1 damage → defeated. Horror assignment to Milan fails.
        assert inv.damage == 1      # 2 - 1 soaked
        assert inv.horror == 3      # All horror to investigator (Milan already gone)
        assert "inst_milan" not in state.cards_in_play

    def test_get_ally_soak_targets(self, setup):
        """get_ally_soak_targets returns correct ally info."""
        state, bus, engine, inv = setup
        targets = engine.get_ally_soak_targets("inv1")
        assert len(targets) == 1
        t = targets[0]
        assert t["instance_id"] == "inst_milan"
        assert t["remaining_health"] == 1
        assert t["remaining_sanity"] == 2

    def test_get_ally_soak_targets_empty_when_no_allies(self, setup):
        """No soak targets when no allies in play."""
        state, bus, engine, inv = setup
        inv.play_area.remove("inst_milan")
        del state.cards_in_play["inst_milan"]
        targets = engine.get_ally_soak_targets("inv1")
        assert len(targets) == 0

    def test_get_ally_soak_targets_excludes_defeated(self, setup):
        """Defeated allies don't appear as soak targets."""
        state, bus, engine, inv = setup
        # Defeat Milan
        engine.deal_damage("inv1", damage=1, damage_assignment={"inst_milan": 1})
        targets = engine.get_ally_soak_targets("inv1")
        assert len(targets) == 0

    def test_partial_ally_damage_accumulates(self, setup):
        """Multiple damage events accumulate on ally."""
        state, bus, engine, inv = setup
        # First, assign 1 horror to Milan
        engine.deal_damage("inv1", horror=1, horror_assignment={"inst_milan": 1})
        milan = state.get_card_instance("inst_milan")
        assert milan.horror == 1
        # Milan still has 1 SAN remaining
        targets = engine.get_ally_soak_targets("inv1")
        assert targets[0]["remaining_sanity"] == 1
        # Second horror defeats Milan
        engine.deal_damage("inv1", horror=1, horror_assignment={"inst_milan": 1})
        assert "inst_milan" not in state.cards_in_play
