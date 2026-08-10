"""Tests for Ambush (Level 1). (03148)

叠加到你所在地点。地点没有调查员时丢弃。
强制 - 敌人生成在被叠加地点后：对其造成2点伤害并丢弃埋伏。
"""

import pytest
from backend.cards.guardian.ambush_lv1 import Ambush, VAR
from backend.engine.game import Game
from backend.models.enums import Action, PlayerClass
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_enemy_data, make_event_data, make_investigator_data,
    make_location_data,
)


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)

    inv_data = make_investigator_data()
    g.register_card_data(inv_data)
    g.register_card_data(make_location_data(connections=["loc2"]))
    g.register_card_data(make_location_data(id="loc2", name="Loc2", connections=["test_location"]))
    g.register_card_data(make_event_data(
        id="ambush_lv1", name="Ambush", cost=2, card_class=PlayerClass.GUARDIAN,
    ))
    g.register_card_data(make_enemy_data(
        id="ghoul", name="Ghoul", fight=3, health=3,
    ))

    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", g.state.get_card_data("test_location"), clues=2)
    g.add_location("loc2", g.state.get_card_data("loc2"), clues=0)
    g.card_registry.register_class(Ambush)

    inv = g.state.get_investigator("inv1")
    inv.hand.append("ambush_lv1")
    inv.resources = 5
    inv.actions_remaining = 3
    return g


def _play_ambush(game):
    game.action_resolver.perform_action("inv1", Action.PLAY, card_id="ambush_lv1")
    impl = next(
        i for i in game.card_registry.active_instances.values()
        if isinstance(i, Ambush)
    )
    return impl


def _spawn_at(game, location_id, instance_id="enemy_1"):
    enemy = CardInstance(
        instance_id=instance_id, card_id="ghoul",
        owner_id="scenario", controller_id="scenario",
    )
    game.state.cards_in_play[instance_id] = enemy
    game.state.get_location(location_id).enemies.append(instance_id)
    return enemy


class TestAmbush:
    def test_attach_on_play(self, game):
        """打出：叠加到当前地点（记录在 scenario.vars）。"""
        _play_ambush(game)
        assert game.state.scenario.vars[VAR] == {"test_location": "inv1"}
        assert "ambush_lv1" in game.state.get_investigator("inv1").discard

    def test_enemy_spawn_triggers_2_damage(self, game):
        """敌人生成在被叠加地点：造成2点伤害并丢弃埋伏。"""
        impl = _play_ambush(game)
        enemy = _spawn_at(game, "test_location")

        triggered = impl.on_enemy_spawned(game.state, "enemy_1", "test_location")
        assert triggered is True
        assert enemy.damage == 2
        assert game.state.scenario.vars[VAR] == {}  # 埋伏已丢弃

    def test_spawn_at_other_location_no_trigger(self, game):
        """敌人生成在其他地点不触发。"""
        impl = _play_ambush(game)
        enemy = _spawn_at(game, "loc2")

        triggered = impl.on_enemy_spawned(game.state, "enemy_1", "loc2")
        assert triggered is False
        assert enemy.damage == 0
        assert game.state.scenario.vars[VAR] == {"test_location": "inv1"}

    def test_discarded_when_location_empties(self, game):
        """最后一名调查员离开被叠加地点：丢弃埋伏。"""
        _play_ambush(game)
        game.action_resolver.perform_action(
            "inv1", Action.MOVE, destination="loc2",
        )
        assert game.state.scenario.vars[VAR] == {}
