"""Tests for Jessica Hyde (Level 1)."""

import pytest
from backend.cards.survivor.jessica_hyde_lv1 import JessicaHyde
from backend.models.enums import (
    Action, ChaosTokenType, GameEvent, PlayerClass, Skill, SlotType,
)
from backend.tests.conftest import (
    make_asset_data, make_investigator_data, make_location_data,
)
from backend.engine.event_bus import EventContext
from backend.engine.game import Game


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)
    inv_data = make_investigator_data(combat=3)
    g.register_card_data(inv_data)
    loc = make_location_data()
    g.register_card_data(loc)
    g.register_card_data(make_asset_data(
        id="jessica_hyde_lv1", name="Jessica Hyde", cost=3,
        card_class=PlayerClass.SURVIVOR, slots=[SlotType.ALLY],
        health=3, sanity=1, traits=["ally", "wayfarer", "cursed"],
    ))
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)
    g.card_registry.register_class(JessicaHyde)
    return g


def _play_jessica(game):
    inv = game.state.get_investigator("inv1")
    inv.hand = ["jessica_hyde_lv1"]
    inv.resources = 5
    assert game.action_resolver.perform_action(
        "inv1", Action.PLAY, card_id="jessica_hyde_lv1") is True
    return inv.play_area[-1]


class TestJessicaHyde:
    def test_card_registered(self, game):
        assert "jessica_hyde_lv1" in game.card_registry.registered_cards

    def test_enters_play_with_2_damage(self, game):
        """入场自带2点伤害。"""
        jessica_id = _play_jessica(game)
        inst = game.state.get_card_instance(jessica_id)
        assert inst.damage == 2

    def test_combat_bonus(self, game):
        """在场时 +1 战斗。"""
        _play_jessica(game)
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]
        result = game.skill_test_engine.run_test("inv1", Skill.COMBAT, 4)
        assert result.modified_skill == 4  # 3 + 1

    def test_heals_1_damage_at_turn_end(self, game):
        """你的回合结束后治愈她1点伤害。"""
        jessica_id = _play_jessica(game)
        game.event_bus.emit(EventContext(
            game_state=game.state, event=GameEvent.INVESTIGATOR_TURN_ENDS,
            investigator_id="inv1",
        ))
        inst = game.state.get_card_instance(jessica_id)
        assert inst.damage == 1
