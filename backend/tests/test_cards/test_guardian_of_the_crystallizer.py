"""Tests for Guardian of the Crystallizer (Level 0 enemy weakness)."""

import pytest
from backend.cards.neutral.guardian_of_the_crystallizer_lv0 import (
    GuardianOfTheCrystallizer,
)
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import GameEvent
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_asset_data, make_enemy_data, make_investigator_data,
    make_location_data,
)


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)
    g.register_card_data(make_investigator_data())
    g.register_card_data(make_location_data())
    g.register_card_data(make_enemy_data(
        id="guardian_of_the_crystallizer_lv0", name="Guardian",
        keywords=["hunter"],
    ))
    g.register_card_data(make_asset_data(
        id="crystallizer_of_dreams", name="Crystallizer of Dreams",
    ))
    g.add_investigator("inv1", g.state.get_card_data("test_investigator"),
                       starting_location="test_location")
    g.add_location("test_location", g.state.get_card_data("test_location"))
    g.card_registry.register_class(GuardianOfTheCrystallizer)
    return g


def _spawn(game):
    enemy = CardInstance(
        instance_id="guardian_1",
        card_id="guardian_of_the_crystallizer_lv0",
        owner_id="inv1", controller_id="scenario",
    )
    game.state.cards_in_play["guardian_1"] = enemy
    game.state.get_investigator("inv1").threat_area.append("guardian_1")
    game.card_registry.activate_card(
        "guardian_of_the_crystallizer_lv0", "guardian_1", game.event_bus,
        chaos_bag=game.chaos_bag,
    )
    ctx = EventContext(
        game_state=game.state, event=GameEvent.CARD_ENTERS_PLAY,
        investigator_id="inv1", target="guardian_1",
        extra={"card_id": "guardian_of_the_crystallizer_lv0"},
    )
    game.event_bus.emit(ctx)
    return enemy


class TestGuardianOfTheCrystallizer:
    def test_enters_play_exhausted_and_set_aside_without_crystallizer(self, game):
        """进场横置；场上无梦境结晶器时被放置一旁（移出游戏）。"""
        _spawn(game)
        # 无结晶器：被移出
        assert "guardian_1" not in game.state.cards_in_play
        assert "guardian_of_the_crystallizer_lv0" in \
            game.state.scenario.vars["out_of_play"]

    def test_stays_with_crystallizer_in_play(self, game):
        """场上有梦境结晶器：保持在场且横置。"""
        inv = game.state.get_investigator("inv1")
        crystal = CardInstance(
            instance_id="crystal_1", card_id="crystallizer_of_dreams",
            owner_id="inv1", controller_id="inv1",
        )
        game.state.cards_in_play["crystal_1"] = crystal
        inv.play_area.append("crystal_1")

        enemy = _spawn(game)
        assert enemy.exhausted is True
        assert "guardian_1" in game.state.cards_in_play
        assert "guardian_1" in inv.threat_area
