"""Tests for Newspaper (Level 2)."""

import pytest
from backend.cards.survivor.newspaper_lv2 import Newspaper
from backend.models.enums import Action, ChaosTokenType, PlayerClass, Skill
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_asset_data, make_investigator_data, make_location_data,
)
from backend.engine.game import Game


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)
    inv_data = make_investigator_data(intellect=3)
    g.register_card_data(inv_data)
    loc = make_location_data(shroud=5, clue_value=3)
    g.register_card_data(loc)
    g.register_card_data(make_asset_data(
        id="newspaper_lv2", name="Newspaper", cost=1,
        card_class=PlayerClass.SURVIVOR, traits=["item"],
    ))
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=3)
    g.card_registry.register_class(Newspaper)
    return g


def _put_in_play(game):
    inv = game.state.get_investigator("inv1")
    iid = game.state.next_instance_id()
    game.state.cards_in_play[iid] = CardInstance(
        instance_id=iid, card_id="newspaper_lv2",
        owner_id="inv1", controller_id="inv1",
    )
    inv.play_area.append(iid)
    game.card_registry.activate_card(
        "newspaper_lv2", iid, game.event_bus, chaos_bag=game.chaos_bag)
    return iid


def _investigate(game, token=ChaosTokenType.ZERO):
    inv = game.state.get_investigator("inv1")
    inv.actions_remaining = 3
    game.chaos_bag.tokens = [token]
    game.action_resolver.perform_action("inv1", Action.INVESTIGATE)
    return game.skill_test_engine._last_result


class TestNewspaper:
    def test_card_registered(self, game):
        assert "newspaper_lv2" in game.card_registry.registered_cards

    def test_plus_2_intellect_while_investigating_without_clues(self, game):
        """无线索时调查+2智力：3+2=5 对 隐蔽5 命中。"""
        _put_in_play(game)
        inv = game.state.get_investigator("inv1")
        inv.clues = 0

        result = _investigate(game)
        assert result.success is True
        assert any(m["reason"] == "newspaper_no_clue_intellect"
                   and m["delta"] == 2
                   for m in result.extra["skill_bonus_sources"])

    def test_no_bonus_when_holding_clues(self, game):
        """持有线索时无加值：3+0 < 5 失败。"""
        _put_in_play(game)
        inv = game.state.get_investigator("inv1")
        inv.clues = 1

        result = _investigate(game)
        assert result.success is False

    def test_no_bonus_outside_investigate(self, game):
        """普通智力检定（非调查行动）不享受加值。"""
        _put_in_play(game)
        inv = game.state.get_investigator("inv1")
        inv.clues = 0
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]

        result = game.skill_test_engine.run_test("inv1", Skill.INTELLECT, 5)
        assert result.success is False  # 3+0 < 5

    def test_reaction_discovers_additional_clue(self, game):
        """无线索时发现线索：额外再发现1个（一次调查共得2线索）。"""
        _put_in_play(game)
        game.state.locations["test_location"].card_data.shroud = 2
        inv = game.state.get_investigator("inv1")
        inv.clues = 0
        loc = game.state.locations["test_location"]

        result = _investigate(game)
        assert result.success is True
        assert inv.clues == 2       # 1正常 + 1报纸反应
        assert loc.clues == 1       # 3 - 2

    def test_no_reaction_when_holding_clues(self, game):
        """持有线索时发现线索：不触发额外发现。"""
        _put_in_play(game)
        game.state.locations["test_location"].card_data.shroud = 2
        inv = game.state.get_investigator("inv1")
        inv.clues = 1
        loc = game.state.locations["test_location"]

        result = _investigate(game)
        assert result.success is True
        assert inv.clues == 2       # 仅正常发现
        assert loc.clues == 2
