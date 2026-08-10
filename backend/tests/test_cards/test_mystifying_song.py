"""Tests for Mystifying Song (Level 0)."""

import pytest
from backend.cards.neutral.mystifying_song_lv0 import MystifyingSong
from backend.engine.game import Game
from backend.models.enums import Action
from backend.tests.conftest import (
    make_event_data, make_investigator_data, make_location_data,
)


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)
    g.register_card_data(make_investigator_data())
    g.register_card_data(make_location_data())
    g.register_card_data(make_event_data(
        id="mystifying_song_lv0", name="Mystifying Song", cost=3, fast=True,
    ))
    g.add_investigator("inv1", g.state.get_card_data("test_investigator"),
                       starting_location="test_location")
    g.add_location("test_location", g.state.get_card_data("test_location"))
    g.card_registry.register_class(MystifyingSong)
    inv = g.state.get_investigator("inv1")
    inv.hand.append("mystifying_song_lv0")
    inv.resources = 5
    return g


class TestMystifyingSong:
    def test_agenda_cannot_advance_this_phase(self, game):
        """打出后本阶段议程不因毁灭阈值推进（推进被回退），并移出游戏。"""
        game.action_resolver.perform_action(
            "inv1", Action.PLAY, card_id="mystifying_song_lv0",
        )
        assert "mystifying_song_lv0" in \
            game.state.scenario.vars["removed_from_game"]

        scenario = game.state.scenario
        scenario.round_number = 2
        scenario.doom_threshold = 1  # 神话阶段放置1毁灭即达阈值
        game.mythos_phase.resolve()
        assert scenario.current_agenda_index == 0  # 未推进

    def test_agenda_advances_normally_without_song(self, game):
        """未打出：议程正常推进。"""
        scenario = game.state.scenario
        scenario.round_number = 2
        scenario.doom_threshold = 1
        game.mythos_phase.resolve()
        assert scenario.current_agenda_index == 1
