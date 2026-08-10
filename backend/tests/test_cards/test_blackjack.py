"""Tests for Blackjack (Level 0)."""

import pytest
from backend.cards.guardian.blackjack_lv0 import Blackjack
from backend.engine.game import Game
from backend.models.enums import Action, CardType, ChaosTokenType, PlayerClass, SlotType
from backend.models.state import CardData, CardInstance
from backend.tests.conftest import make_enemy_data, make_investigator_data, make_location_data


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)

    inv_data = make_investigator_data(combat=2)
    g.register_card_data(inv_data)

    loc = make_location_data()
    g.register_card_data(loc)

    bj_data = CardData(
        id="blackjack_lv0", name="Blackjack", name_cn="金属棍棒",
        type=CardType.ASSET, card_class=PlayerClass.GUARDIAN, cost=1,
        slots=[SlotType.HAND], traits=["item", "weapon", "melee"],
    )
    g.register_card_data(bj_data)

    enemy_data = make_enemy_data(fight=3, health=3)
    g.register_card_data(enemy_data)

    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)

    g.card_registry.register_class(Blackjack)
    return g


def _equip_blackjack(game):
    inv = game.state.get_investigator("inv1")
    instance_id = game.state.next_instance_id()
    card_inst = CardInstance(
        instance_id=instance_id, card_id="blackjack_lv0",
        owner_id="inv1", controller_id="inv1",
        slot_used=[SlotType.HAND],
    )
    game.state.cards_in_play[instance_id] = card_inst
    inv.play_area.append(instance_id)
    game.card_registry.activate_card("blackjack_lv0", instance_id, game.event_bus)
    return instance_id


def _spawn_enemy(game):
    enemy = CardInstance(
        instance_id="enemy_1", card_id="test_enemy",
        owner_id="scenario", controller_id="scenario",
    )
    game.state.cards_in_play["enemy_1"] = enemy
    inv = game.state.get_investigator("inv1")
    inv.threat_area.append("enemy_1")
    return enemy


class TestBlackjack:
    def test_card_id(self):
        assert Blackjack.card_id == "blackjack_lv0"

    def test_combat_bonus_applies(self, game):
        """用金属棍棒攻击 +1 战斗：战斗2 + 棍棒1 = 3 vs 3 → 命中。"""
        bj_id = _equip_blackjack(game)
        enemy = _spawn_enemy(game)
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]

        inv = game.state.get_investigator("inv1")
        inv.actions_remaining = 3
        game.action_resolver.perform_action(
            "inv1", Action.FIGHT,
            enemy_instance_id="enemy_1",
            weapon_instance_id=bj_id,
        )
        # 无+1则 2 vs 3 失手；有+1则命中造成1伤害
        assert enemy.damage == 1

    def test_no_bonus_without_weapon_source(self, game):
        """徒手攻击（不指定武器）不享受棍棒加成。"""
        _equip_blackjack(game)
        enemy = _spawn_enemy(game)
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]

        inv = game.state.get_investigator("inv1")
        inv.actions_remaining = 3
        game.action_resolver.perform_action(
            "inv1", Action.FIGHT,
            enemy_instance_id="enemy_1",
        )
        # 战斗2 vs 3 → 失手
        assert enemy.damage == 0
