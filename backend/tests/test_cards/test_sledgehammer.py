"""Tests for Sledgehammer (Level 0 / Level 4). (08094/08096)

lv0：1行动 -1战斗/+1伤害；2行动 +2战斗/+2伤害。
lv4：1行动 +1战斗/+1伤害；3行动 +5战斗/+5伤害。
"""

import pytest

from backend.cards.guardian.sledgehammer_lv0 import Sledgehammer
from backend.cards.guardian.sledgehammer_lv4 import SledgehammerLv4
from backend.engine.game import Game
from backend.models.enums import (
    Action, CardType, ChaosTokenType, PlayerClass, SlotType,
)
from backend.models.state import CardData, CardInstance
from backend.tests.conftest import (
    make_enemy_data, make_investigator_data, make_location_data,
)


def _game(impl_cls, card_id, enemy_fight=4, enemy_health=10):
    g = Game("test")
    g.chaos_bag.seed(42)
    g.chaos_bag.tokens = [ChaosTokenType.ZERO]
    inv_data = make_investigator_data(combat=3)
    g.register_card_data(inv_data)
    loc = make_location_data()
    g.register_card_data(loc)
    g.register_card_data(CardData(
        id=card_id, name="Sledgehammer", name_cn="长柄大锤",
        type=CardType.ASSET, card_class=PlayerClass.GUARDIAN, cost=3,
        slots=[SlotType.HAND, SlotType.HAND],
        traits=["item", "tool", "weapon", "melee"],
    ))
    g.register_card_data(make_enemy_data(
        id="ghoul", fight=enemy_fight, health=enemy_health))

    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", g.state.get_card_data("test_location"))
    g.card_registry.register_class(impl_cls)

    hammer = CardInstance(
        instance_id="hammer_1", card_id=card_id,
        owner_id="inv1", controller_id="inv1",
        slot_used=[SlotType.HAND, SlotType.HAND],
    )
    g.state.cards_in_play["hammer_1"] = hammer
    inv = g.state.get_investigator("inv1")
    inv.play_area.append("hammer_1")
    inv.actions_remaining = 3
    impl = g.card_registry.activate_card(
        card_id, "hammer_1", g.event_bus, chaos_bag=g.chaos_bag)

    enemy = CardInstance(
        instance_id="enemy_1", card_id="ghoul",
        owner_id="scenario", controller_id="scenario",
    )
    g.state.cards_in_play["enemy_1"] = enemy
    inv.threat_area.append("enemy_1")
    return g, impl


class TestSledgehammerLv0:
    def test_light_attack(self):
        """轻击：3战斗-1=2 vs 战斗4 → 失败无伤害；换战斗3敌人则成功+1伤害。"""
        game, impl = _game(Sledgehammer, "sledgehammer_lv0", enemy_fight=4)
        assert impl.activate_light(game.state, "inv1") is True
        game.action_resolver.perform_action(
            "inv1", Action.FIGHT, enemy_instance_id="enemy_1",
            weapon_instance_id="hammer_1",
        )
        # -1战斗：2 < 4 失败
        assert game.state.get_card_instance("enemy_1").damage == 0

    def test_light_attack_damage_bonus(self):
        """轻击命中（战斗2敌人：3-1=2 ≥ 2 成功）：伤害=1基础+1=2。"""
        game, impl = _game(Sledgehammer, "sledgehammer_lv0", enemy_fight=2)
        impl.activate_light(game.state, "inv1")
        game.action_resolver.perform_action(
            "inv1", Action.FIGHT, enemy_instance_id="enemy_1",
            weapon_instance_id="hammer_1",
        )
        assert game.state.get_card_instance("enemy_1").damage == 2

    def test_heavy_attack(self):
        """重击：3战斗+2=5 vs 战斗4 → 成功，伤害=1+2=3。"""
        game, impl = _game(Sledgehammer, "sledgehammer_lv0", enemy_fight=4)
        assert impl.activate_heavy(game.state, "inv1") is True
        game.action_resolver.perform_action(
            "inv1", Action.FIGHT, enemy_instance_id="enemy_1",
            weapon_instance_id="hammer_1",
        )
        assert game.state.get_card_instance("enemy_1").damage == 3

    def test_mode_cleared_after_test(self):
        """一次攻击后模式清除：未武装时无修正。"""
        game, impl = _game(Sledgehammer, "sledgehammer_lv0", enemy_fight=4)
        impl.activate_heavy(game.state, "inv1")
        game.action_resolver.perform_action(
            "inv1", Action.FIGHT, enemy_instance_id="enemy_1",
            weapon_instance_id="hammer_1",
        )
        # 第二次攻击未武装：3 vs 4 失败，无伤害增加
        game.state.get_investigator("inv1").actions_remaining = 3
        enemy = game.state.get_card_instance("enemy_1")
        before = enemy.damage
        game.action_resolver.perform_action(
            "inv1", Action.FIGHT, enemy_instance_id="enemy_1",
            weapon_instance_id="hammer_1",
        )
        assert enemy.damage == before


class TestSledgehammerLv4:
    def test_light_attack(self):
        """lv4轻击：3+1=4 vs 战斗4 → 成功，伤害=1+1=2。"""
        game, impl = _game(SledgehammerLv4, "sledgehammer_lv4", enemy_fight=4)
        impl.activate_light(game.state, "inv1")
        game.action_resolver.perform_action(
            "inv1", Action.FIGHT, enemy_instance_id="enemy_1",
            weapon_instance_id="hammer_1",
        )
        assert game.state.get_card_instance("enemy_1").damage == 2

    def test_heavy_attack(self):
        """lv4重击：3+5=8 vs 战斗7 → 成功，伤害=1+5=6。"""
        game, impl = _game(SledgehammerLv4, "sledgehammer_lv4",
                           enemy_fight=7, enemy_health=10)
        impl.activate_heavy(game.state, "inv1")
        game.action_resolver.perform_action(
            "inv1", Action.FIGHT, enemy_instance_id="enemy_1",
            weapon_instance_id="hammer_1",
        )
        assert game.state.get_card_instance("enemy_1").damage == 6
