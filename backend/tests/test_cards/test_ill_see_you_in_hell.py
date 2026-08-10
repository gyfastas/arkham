"""Tests for "I'll see you in hell!" (Level 0). (03189)

击败与你交战的每个非精英敌人。你被击败并承受1点肉体创伤。
本行动不会引起趁乱攻击。
"""

import pytest
from backend.cards.guardian.ill_see_you_in_hell_lv0 import IllSeeYouInHell
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

    inv_data = make_investigator_data(health=7, sanity=7)
    g.register_card_data(inv_data)
    g.register_card_data(make_location_data())
    g.register_card_data(make_event_data(
        id="ill_see_you_in_hell_lv0", name='"I\'ll see you in hell!"', cost=0,
        card_class=PlayerClass.GUARDIAN,
    ))
    g.register_card_data(make_enemy_data(
        id="ghoul", name="Ghoul", fight=2, health=5, damage=1, horror=1,
    ))
    g.register_card_data(make_enemy_data(
        id="elite_boss", name="Boss", fight=5, health=9,
        damage=2, horror=2, keywords=["elite"],
    ))

    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", g.state.get_card_data("test_location"), clues=2)
    g.card_registry.register_class(IllSeeYouInHell)

    inv = g.state.get_investigator("inv1")
    inv.hand.append("ill_see_you_in_hell_lv0")
    inv.actions_remaining = 3
    return g


def _spawn_engaged(game, card_id, instance_id):
    enemy = CardInstance(
        instance_id=instance_id, card_id=card_id,
        owner_id="scenario", controller_id="scenario",
    )
    game.state.cards_in_play[instance_id] = enemy
    game.state.get_investigator("inv1").threat_area.append(instance_id)
    return enemy


class TestIllSeeYouInHell:
    def test_defeats_non_elite_engaged_and_self(self, game):
        """交战的非精英敌人全部被击败；精英保留；自己被击败+1肉体创伤。"""
        _spawn_engaged(game, "ghoul", "enemy_1")
        _spawn_engaged(game, "ghoul", "enemy_2")
        boss = _spawn_engaged(game, "elite_boss", "enemy_3")
        inv = game.state.get_investigator("inv1")

        ok = game.action_resolver.perform_action(
            "inv1", Action.PLAY, card_id="ill_see_you_in_hell_lv0",
        )
        assert ok is True

        # 非精英敌人被击败离场（入遭遇弃牌堆）
        assert "enemy_1" not in inv.threat_area
        assert "enemy_2" not in inv.threat_area
        assert game.state.get_card_instance("enemy_1") is None
        assert game.state.get_card_instance("enemy_2") is None
        assert game.state.scenario.encounter_discard.count("ghoul") == 2
        # 精英敌人保留（未被击败）
        assert "enemy_3" in inv.threat_area
        assert boss.damage == 0
        # 自己被击败并承受1点肉体创伤
        assert inv.is_defeated is True
        assert getattr(inv, "physical_trauma", 0) == 1

    def test_play_does_not_provoke_aoo(self, game):
        """打出行动不引起趁乱攻击（精英敌人仍交战但未借机攻击）。"""
        _spawn_engaged(game, "elite_boss", "enemy_3")  # 未横置，正常会AoO
        inv = game.state.get_investigator("inv1")

        game.action_resolver.perform_action(
            "inv1", Action.PLAY, card_id="ill_see_you_in_hell_lv0",
        )
        # 伤害恰好等于生命上限（自我击败），没有AoO额外造成的2伤害
        assert inv.damage == inv.health
