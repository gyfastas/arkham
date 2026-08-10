"""Tests for Anatomical Diagrams (Level 0).

官方：快速。任意调查员回合中可打出。仅有至少5点剩余理智时才能打出。
选择你所在地点1个非精英敌人，直到当前调查员回合结束，该敌人-2战斗力、-2闪避值。
"""

import pytest

from backend.cards.seeker.anatomical_diagrams_lv0 import AnatomicalDiagrams
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import Action, ChaosTokenType, GameEvent
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_enemy_data, make_event_data, make_investigator_data,
    make_location_data,
)


@pytest.fixture
def game():
    g = Game("test_anatomical_diagrams")
    g.chaos_bag.seed(42)

    inv_data = make_investigator_data(combat=3, agility=3, sanity=7)
    g.register_card_data(inv_data)
    loc_data = make_location_data(id="loc_a", clue_value=2)
    g.register_card_data(loc_data)
    g.add_investigator("player", inv_data, starting_location="loc_a")
    g.add_location("loc_a", loc_data, clues=2)

    # 战斗力/闪避值均为5：3技能值不削弱时无法命中
    enemy_data = make_enemy_data(id="ghoul", name="Ghoul",
                                 fight=5, evade=5, health=10)
    g.register_card_data(enemy_data)
    g.state.cards_in_play["enemy_1"] = CardInstance(
        instance_id="enemy_1", card_id="ghoul",
        owner_id="scenario", controller_id="scenario",
    )
    g.state.get_investigator("player").threat_area.append("enemy_1")

    g.register_card_data(make_event_data(
        id="anatomical_diagrams_lv0", cost=1, fast=True))
    g.card_registry.register_class(AnatomicalDiagrams)
    g.chaos_bag.tokens = [ChaosTokenType.ZERO]
    return g


def _play(game):
    impl = AnatomicalDiagrams("ad_temp")
    impl.register(game.event_bus, "ad_temp")
    ctx = EventContext(
        game_state=game.state,
        event=GameEvent.CARD_PLAYED,
        investigator_id="player",
        extra={"card_id": "anatomical_diagrams_lv0"},
    )
    game.event_bus.emit(ctx)
    return ctx


class TestAnatomicalDiagrams:
    def test_play_marks_non_elite_enemy(self, game):
        ctx = _play(game)
        assert ctx.extra["anatomical_diagrams_target"] == "enemy_1"

    def test_fight_difficulty_reduced(self, game):
        """战斗力5的敌人：未削弱时3战斗力无法命中；削弱后（难度3）命中。"""
        _play(game)
        game.action_resolver.perform_action(
            "player", Action.FIGHT, enemy_instance_id="enemy_1")
        enemy = game.state.get_card_instance("enemy_1")
        assert enemy.damage == 1  # 命中造成1点基础伤害

    def test_evade_difficulty_reduced(self, game):
        """闪避值5的敌人：削弱后（难度3）3敏捷可成功。"""
        _play(game)
        game.action_resolver.perform_action(
            "player", Action.EVADE, enemy_instance_id="enemy_1")
        inv = game.state.get_investigator("player")
        enemy = game.state.get_card_instance("enemy_1")
        assert enemy.exhausted is True
        assert "enemy_1" not in inv.threat_area

    def test_requires_5_remaining_sanity(self, game):
        """剩余理智<5时效果不生效，战斗无法命中。"""
        inv = game.state.get_investigator("player")
        inv.horror = 3  # 剩余理智 4
        ctx = _play(game)
        assert ctx.extra.get("anatomical_diagrams_failed") == "sanity"
        assert "anatomical_diagrams_target" not in ctx.extra

        game.action_resolver.perform_action(
            "player", Action.FIGHT, enemy_instance_id="enemy_1")
        enemy = game.state.get_card_instance("enemy_1")
        assert enemy.damage == 0

    def test_expires_at_turn_end(self, game):
        """当前调查员回合结束后削弱过期。"""
        _play(game)
        game.event_bus.emit(EventContext(
            game_state=game.state,
            event=GameEvent.INVESTIGATOR_TURN_ENDS,
            investigator_id="player",
        ))
        game.action_resolver.perform_action(
            "player", Action.FIGHT, enemy_instance_id="enemy_1")
        enemy = game.state.get_card_instance("enemy_1")
        assert enemy.damage == 0
