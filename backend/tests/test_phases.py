"""Tests for game phases."""

import pytest
from backend.engine.game import Game
from backend.models.enums import Action, ChaosTokenType, GameEvent, Phase
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_enemy_data, make_investigator_data, make_location_data,
)


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)

    inv_data = make_investigator_data(combat=4, agility=3)
    g.register_card_data(inv_data)

    loc1 = make_location_data(id="loc1", shroud=2, clue_value=3, connections=["loc2"])
    loc2 = make_location_data(id="loc2", shroud=3, clue_value=2, connections=["loc1"])
    g.register_card_data(loc1)
    g.register_card_data(loc2)

    g.add_investigator("inv1", inv_data, starting_location="loc1", deck=["c1", "c2", "c3", "c4", "c5", "c6", "c7"])
    g.add_location("loc1", loc1, clues=3)
    g.add_location("loc2", loc2, clues=2)

    g.state.scenario.encounter_deck = ["enc1", "enc2"]
    g.state.scenario.doom_threshold = 5

    return g


class TestMythosPhase:
    def test_mythos_skipped_round_1(self, game):
        game.state.scenario.round_number = 1
        game.mythos_phase.resolve()
        # Doom should NOT be placed on round 1
        assert game.state.scenario.doom_on_agenda == 0

    def test_mythos_places_doom(self, game):
        game.state.scenario.round_number = 2
        game.mythos_phase.resolve()
        assert game.state.scenario.doom_on_agenda == 1

    def test_mythos_draws_encounter_cards(self, game):
        game.state.scenario.round_number = 2
        initial_enc = len(game.state.scenario.encounter_deck)
        game.mythos_phase.resolve()
        assert len(game.state.scenario.encounter_deck) == initial_enc - 1

    def test_agenda_advances_at_threshold(self, game):
        game.state.scenario.round_number = 2
        game.state.scenario.doom_on_agenda = 4  # +1 = 5 = threshold
        game.mythos_phase.resolve()
        assert game.state.scenario.current_agenda_index == 1
        assert game.state.scenario.doom_on_agenda == 0  # reset after advance


class TestInvestigationPhase:
    def test_investigator_gets_3_actions(self, game):
        action_count = [0]

        def callback(inv_id, actions, resolver):
            action_count[0] += 1
            if action_count[0] <= 3:
                return (Action.RESOURCE, {})
            return None

        game.investigation_phase.resolve(action_callback=callback)
        inv = game.state.get_investigator("inv1")
        assert inv.actions_remaining == 0

    def test_no_callback_no_actions(self, game):
        game.investigation_phase.resolve()
        # Without callback, no actions taken
        inv = game.state.get_investigator("inv1")
        assert inv.actions_remaining == 3


class TestEnemyPhase:
    def test_enemy_attacks_engaged_investigator(self, game):
        enemy_data = make_enemy_data(damage=2, horror=1)
        game.register_card_data(enemy_data)

        enemy = CardInstance(
            instance_id="enemy_1", card_id="test_enemy",
            owner_id="scenario", controller_id="scenario",
        )
        game.state.cards_in_play["enemy_1"] = enemy
        inv = game.state.get_investigator("inv1")
        inv.threat_area.append("enemy_1")

        game.enemy_phase.resolve()
        assert inv.damage == 2
        assert inv.horror == 1
        assert enemy.exhausted

    def test_exhausted_enemy_does_not_attack(self, game):
        enemy_data = make_enemy_data(damage=2, horror=1)
        game.register_card_data(enemy_data)

        enemy = CardInstance(
            instance_id="enemy_1", card_id="test_enemy",
            owner_id="scenario", controller_id="scenario",
            exhausted=True,
        )
        game.state.cards_in_play["enemy_1"] = enemy
        inv = game.state.get_investigator("inv1")
        inv.threat_area.append("enemy_1")

        game.enemy_phase.resolve()
        assert inv.damage == 0

    def test_hunter_moves_toward_investigator(self, game):
        enemy_data = make_enemy_data(id="hunter_enemy", keywords=["hunter"])
        game.register_card_data(enemy_data)

        enemy = CardInstance(
            instance_id="hunter_1", card_id="hunter_enemy",
            owner_id="scenario", controller_id="scenario",
        )
        game.state.cards_in_play["hunter_1"] = enemy
        loc2 = game.state.get_location("loc2")
        loc2.enemies.append("hunter_1")

        # inv1 is at loc1, connected to loc2
        game.enemy_phase.resolve()
        # Hunter should move from loc2 to loc1 and engage inv1
        inv = game.state.get_investigator("inv1")
        assert "hunter_1" in inv.threat_area
        assert "hunter_1" not in loc2.enemies


class TestUpkeepPhase:
    def test_ready_exhausted_cards(self, game):
        from backend.models.state import CardInstance
        card = CardInstance(
            instance_id="asset_1", card_id="some_asset",
            owner_id="inv1", controller_id="inv1",
            exhausted=True,
        )
        game.state.cards_in_play["asset_1"] = card

        game.upkeep_phase.resolve()
        assert not card.exhausted

    def test_draw_and_resource(self, game):
        inv = game.state.get_investigator("inv1")
        initial_hand = len(inv.hand)
        initial_resources = inv.resources

        game.upkeep_phase.resolve()
        assert len(inv.hand) == initial_hand + 1
        assert inv.resources == initial_resources + 1

    def test_hand_size_check(self, game):
        inv = game.state.get_investigator("inv1")
        # Fill hand to 10 cards
        inv.hand = [f"card_{i}" for i in range(10)]

        game.upkeep_phase.resolve()
        # After upkeep draws 1 more = 11, must discard to 8
        # Actually after draw it's 11, discard down to 8 = discard 3
        assert len(inv.hand) == 8


class TestFullRound:
    def test_round_increments(self, game):
        assert game.state.scenario.round_number == 0
        game.run_round()
        assert game.state.scenario.round_number == 1

    def test_multiple_rounds(self, game):
        game.run_round()
        game.run_round()
        assert game.state.scenario.round_number == 2
        # Round 2 has mythos, so doom should be placed
        assert game.state.scenario.doom_on_agenda >= 1
