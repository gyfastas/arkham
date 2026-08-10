"""Tests for Sled Dog (Level 0)."""

import pytest

from backend.cards.neutral.sled_dog_lv0 import SledDog
from backend.engine.game import Game
from backend.models.enums import Action, ChaosTokenType, CardType, PlayerClass
from backend.models.state import CardData, CardInstance
from backend.tests.conftest import make_enemy_data, make_investigator_data, make_location_data


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)
    inv_data = make_investigator_data(combat=3)
    g.register_card_data(inv_data)
    loc = make_location_data()
    g.register_card_data(loc)
    g.register_card_data(CardData(
        id="sled_dog_lv0", name="Sled Dog", name_cn="雪橇犬",
        type=CardType.ASSET, card_class=PlayerClass.NEUTRAL, cost=3,
        traits=["ally", "creature"], skill_icons={"combat": 1},
    ))
    g.register_card_data(make_enemy_data(fight=4, health=10))
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=2)
    g.card_registry.register_class(SledDog)
    return g


def _equip_dogs(game, count=2):
    inv = game.state.get_investigator("inv1")
    ids = []
    for i in range(count):
        iid = f"dog_{i+1}"
        ci = CardInstance(
            instance_id=iid, card_id="sled_dog_lv0",
            owner_id="inv1", controller_id="inv1",
        )
        game.state.cards_in_play[iid] = ci
        inv.play_area.append(iid)
        ids.append(iid)
    impl = SledDog(ids[0])
    impl.register(game.event_bus, ids[0])
    return ids, impl


def _spawn_enemy(game):
    enemy = CardInstance(
        instance_id="enemy_1", card_id="test_enemy",
        owner_id="scenario", controller_id="scenario",
    )
    game.state.cards_in_play["enemy_1"] = enemy
    game.state.get_investigator("inv1").threat_area.append("enemy_1")
    return enemy


class TestSledDog:
    def test_fight_with_two_dogs(self, game):
        """横置2只犬战斗：+2战斗，造成2点伤害（代替标准1点）。"""
        ids, impl = _equip_dogs(game, 2)
        enemy = _spawn_enemy(game)
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]
        inv = game.state.get_investigator("inv1")
        inv.actions_remaining = 3

        assert impl.activate_fight(game.state, "inv1", x=2) is True
        assert game.state.get_card_instance("dog_1").exhausted is True
        assert game.state.get_card_instance("dog_2").exhausted is True

        game.action_resolver.perform_action(
            "inv1", Action.FIGHT,
            enemy_instance_id="enemy_1", weapon_instance_id="dog_1",
        )
        # 战斗3 + 2 = 5 vs 4 → 成功；伤害 = X = 2
        assert enemy.damage == 2

    def test_fight_with_one_dog_standard_damage(self, game):
        """横置1只犬：+1战斗，1点伤害。"""
        ids, impl = _equip_dogs(game, 1)
        enemy = _spawn_enemy(game)
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]
        inv = game.state.get_investigator("inv1")
        inv.actions_remaining = 3

        assert impl.activate_fight(game.state, "inv1", x=1) is True
        game.action_resolver.perform_action(
            "inv1", Action.FIGHT,
            enemy_instance_id="enemy_1", weapon_instance_id="dog_1",
        )
        # 战斗3 + 1 = 4 vs 4 → 成功；伤害 = 1
        assert enemy.damage == 1

    def test_cannot_exhaust_more_than_available(self, game):
        """横置数量超过可用犬数：失败。"""
        ids, impl = _equip_dogs(game, 1)
        assert impl.activate_fight(game.state, "inv1", x=2) is False
        assert game.state.get_card_instance("dog_1").exhausted is False

    def test_move_exhausts_dogs(self, game):
        """移动能力：横置X只犬（移动本身由会话层执行）。"""
        ids, impl = _equip_dogs(game, 2)
        assert impl.activate_move(game.state, "inv1", x=2) is True
        assert game.state.get_card_instance("dog_1").exhausted is True
        assert game.state.get_card_instance("dog_2").exhausted is True
