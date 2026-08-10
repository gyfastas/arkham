"""Tests for Eavesdrop (Level 0)."""

import pytest
from backend.cards.rogue.eavesdrop_lv0 import Eavesdrop
from backend.engine.game import Game
from backend.models.enums import ChaosTokenType, Skill
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_enemy_data, make_event_data, make_investigator_data,
    make_location_data,
)


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)

    inv_data = make_investigator_data(intellect=3)
    g.register_card_data(inv_data)
    loc = make_location_data(clue_value=3)
    g.register_card_data(loc)
    g.register_card_data(make_event_data(id="eavesdrop_lv0", name="Eavesdrop"))
    g.register_card_data(make_enemy_data(evade=4))

    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=3)

    enemy = CardInstance(
        instance_id="enemy_1", card_id="test_enemy",
        owner_id="scenario", controller_id="scenario",
    )
    g.state.cards_in_play["enemy_1"] = enemy
    g.state.locations["test_location"].enemies.append("enemy_1")

    g.card_registry.register_class(Eavesdrop)
    return g


def _play(game):
    """经引擎打出窃听（注册临时实现并发出 CARD_PLAYED）。"""
    inv = game.state.get_investigator("inv1")
    inv.hand.append("eavesdrop_lv0")
    game.card_registry.activate_card(
        "eavesdrop_lv0", "eav_temp", game.event_bus,
        chaos_bag=game.chaos_bag)
    from backend.engine.event_bus import EventContext
    from backend.models.enums import GameEvent
    game.event_bus.emit(EventContext(
        game_state=game.state, event=GameEvent.CARD_PLAYED,
        investigator_id="inv1", source="eav_temp",
        extra={"card_id": "eavesdrop_lv0"},
    ))
    inv.hand.remove("eavesdrop_lv0")
    inv.discard.append("eavesdrop_lv0")


class TestEavesdrop:
    def test_difficulty_set_to_evade_and_discover_2(self, game):
        """检定难度强制为敌人躲避值(4)；成功发现2个线索。"""
        _play(game)
        game.chaos_bag.tokens = [ChaosTokenType.PLUS_1]
        # 会话层以任意难度发起（实现会在 SKILL_TEST_BEGINS 改写为4）
        result = game.skill_test_engine.run_test("inv1", Skill.INTELLECT, 99)
        assert result.difficulty == 4
        assert result.success is True  # 3+1 vs 4
        inv = game.state.get_investigator("inv1")
        assert inv.clues == 2
        assert game.state.locations["test_location"].clues == 1
        assert result.extra["eavesdrop_clues"] == 2

    def test_failure_no_clues(self, game):
        _play(game)
        game.chaos_bag.tokens = [ChaosTokenType.MINUS_3]
        result = game.skill_test_engine.run_test("inv1", Skill.INTELLECT, 99)
        assert result.success is False
        inv = game.state.get_investigator("inv1")
        assert inv.clues == 0
        assert game.state.locations["test_location"].clues == 3

    def test_clues_capped_by_location(self, game):
        """地点仅剩1个线索时只拿1个。"""
        game.state.locations["test_location"].clues = 1
        _play(game)
        game.chaos_bag.tokens = [ChaosTokenType.PLUS_1]
        result = game.skill_test_engine.run_test("inv1", Skill.INTELLECT, 99)
        assert result.success is True
        inv = game.state.get_investigator("inv1")
        assert inv.clues == 1
        assert result.extra["eavesdrop_clues"] == 1
