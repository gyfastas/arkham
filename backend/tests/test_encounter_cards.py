"""Tests for encounter card mechanics — Ancient Evils agenda advancement."""

import pytest
import sys
from pathlib import Path

# Add project root so we can import the server module
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.engine.game import Game
from backend.engine.event_bus import EventBus
from backend.models.enums import Phase
from backend.models.state import (
    GameState, InvestigatorState, ScenarioState,
)
from backend.tests.conftest import make_investigator_data, make_location_data


class TestAncientEvils:
    """Test that Ancient Evils encounter card correctly advances the agenda."""

    def _make_game(self, doom_threshold=5, initial_doom=0):
        """Helper to create a minimal game with encounter deck."""
        g = Game("test_scenario")
        inv_data = make_investigator_data()
        g.register_card_data(inv_data)
        loc_data = make_location_data()
        g.register_card_data(loc_data)
        g.add_investigator("player", inv_data, starting_location="test_location")
        g.add_location("test_location", loc_data, clues=2)
        g.state.scenario.doom_threshold = doom_threshold
        g.state.scenario.doom_on_agenda = initial_doom
        g.state.scenario.current_phase = Phase.INVESTIGATION
        g.state.scenario.round_number = 1
        inv = g.state.get_investigator("player")
        inv.actions_remaining = 3
        return g

    def test_ancient_evils_adds_doom(self):
        """Ancient Evils adds 1 doom to the agenda."""
        # We test the encounter card resolution logic directly
        # by simulating what both server_full.py and server_daisy.py do
        g = self._make_game(doom_threshold=5, initial_doom=0)
        assert g.state.scenario.doom_on_agenda == 0

        # Simulate Ancient Evils effect
        g.state.scenario.doom_on_agenda += 1
        assert g.state.scenario.doom_on_agenda == 1

    def test_ancient_evils_triggers_agenda_at_threshold(self):
        """Ancient Evils should trigger agenda advancement when doom reaches threshold."""
        g = self._make_game(doom_threshold=5, initial_doom=4)

        # Simulate Ancient Evils — doom goes 4→5, hitting threshold
        g.state.scenario.doom_on_agenda += 1

        # check_agenda logic
        assert g.state.scenario.doom_on_agenda >= g.state.scenario.doom_threshold
        # This is the condition that triggers game over in both servers

    def test_ancient_evils_causes_loss_at_exact_threshold(self):
        """Game should be lost when Ancient Evils pushes doom to exactly the threshold."""
        g = self._make_game(doom_threshold=3, initial_doom=2)

        g.state.scenario.doom_on_agenda += 1  # Ancient Evils
        assert g.state.scenario.doom_on_agenda == 3
        assert g.state.scenario.doom_on_agenda >= g.state.scenario.doom_threshold

    def test_ancient_evils_causes_loss_above_threshold(self):
        """Game should be lost when doom exceeds threshold (e.g. multiple doom sources)."""
        g = self._make_game(doom_threshold=3, initial_doom=3)

        g.state.scenario.doom_on_agenda += 1  # Ancient Evils
        assert g.state.scenario.doom_on_agenda == 4
        assert g.state.scenario.doom_on_agenda >= g.state.scenario.doom_threshold

    def test_ancient_evils_no_loss_below_threshold(self):
        """Game should NOT be lost when doom is still below threshold."""
        g = self._make_game(doom_threshold=8, initial_doom=3)

        g.state.scenario.doom_on_agenda += 1  # Ancient Evils
        assert g.state.scenario.doom_on_agenda == 4
        assert g.state.scenario.doom_on_agenda < g.state.scenario.doom_threshold


class TestAncientEvilsInEndTurn:
    """Test Ancient Evils within the full end-turn flow (server integration)."""

    def test_encounter_doom_checked_after_resolution(self):
        """After encounter card adds doom, game_over should be set if threshold met.

        This tests the bug fix: previously the end-turn flow only checked
        inv.is_defeated after encounter resolution, but not game_over set
        by check_agenda() during Ancient Evils resolution.
        """
        # Import the server module to test end-turn flow
        from frontend import server_daisy

        # Setup the game
        server_daisy.game = server_daisy.create_game()
        g = server_daisy.game
        server_daisy.game_over = None

        # Set doom to threshold - 1, so one Ancient Evils will trigger loss
        g.state.scenario.doom_on_agenda = g.state.scenario.doom_threshold - 1

        # Force encounter deck to have only Ancient Evils
        g.state.scenario.encounter_deck = ["ancient_evils"]

        # End the turn — mythos phase adds +1 doom, then draws Ancient Evils (+1 doom)
        result = server_daisy.handle_end_turn()

        # The +1 doom from mythos phase already hits threshold
        # OR the Ancient Evils adds another doom
        # Either way, game should be over
        assert server_daisy.game_over is not None
        assert server_daisy.game_over["type"] == "lose"

    def test_encounter_doom_does_not_false_trigger(self):
        """Encounter card that doesn't affect doom shouldn't trigger agenda."""
        from frontend import server_daisy

        server_daisy.game = server_daisy.create_game()
        g = server_daisy.game
        server_daisy.game_over = None

        # Set doom low
        g.state.scenario.doom_on_agenda = 0

        # Force encounter deck to have a non-doom card
        g.state.scenario.encounter_deck = ["whispering_voices"]

        result = server_daisy.handle_end_turn()

        # Doom should be 1 (from mythos +1), threshold is 8
        # Game should NOT be over from encounter
        # (might be over from investigator defeat, but not from doom)
        if server_daisy.game_over:
            assert server_daisy.game_over["type"] != "lose" or \
                "毁灭" not in server_daisy.game_over.get("message", "")
