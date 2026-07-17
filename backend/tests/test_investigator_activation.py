"""Tests for investigator ability activation during Game.setup().

Game.setup() should auto-activate CardImplementation classes registered under
an investigator's card_id (e.g. "zoey_samaras"), so abilities work in real
games without manual registration.
"""

import pytest

from backend.engine.game import Game
from backend.tests.conftest import make_investigator_data, make_location_data


def _make_game(inv_card_id: str = "zoey_samaras") -> Game:
    g = Game("test_scenario")
    inv_data = make_investigator_data(id=inv_card_id)
    g.register_card_data(inv_data)
    loc_data = make_location_data(clue_value=3, connections=[])
    g.register_card_data(loc_data)
    g.add_investigator("player1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc_data, clues=3)
    return g


class TestInvestigatorAbilityActivation:
    def test_setup_activates_registered_investigator_impl(self):
        """Investigators with a registered implementation get activated on setup."""
        g = _make_game("zoey_samaras")
        g.setup()
        assert "investigator_player1" in g.card_registry.active_instances

    def test_setup_skips_investigator_without_impl(self):
        """Investigators without a registered implementation are skipped."""
        g = _make_game("test_investigator")  # no impl registered for this id
        g.setup()
        assert "investigator_player1" not in g.card_registry.active_instances

    def test_activated_impl_is_correct_class(self):
        from backend.cards.guardian.zoey_samaras import ZoeySamaras
        g = _make_game("zoey_samaras")
        g.setup()
        impl = g.card_registry.active_instances["investigator_player1"]
        assert isinstance(impl, ZoeySamaras)
