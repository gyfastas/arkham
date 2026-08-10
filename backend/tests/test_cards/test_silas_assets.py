"""Tests for Sea Change Harpoon & Silas's Net (Level 0) — Silas signature assets."""

import pytest

from backend.cards.neutral.sea_change_harpoon_lv0 import SeaChangeHarpoon
from backend.cards.neutral.silass_net_lv0 import SilassNet
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import Action, ChaosTokenType, CardType, GameEvent, PlayerClass
from backend.models.state import CardData, CardInstance
from backend.tests.conftest import (
    make_enemy_data, make_investigator_data, make_location_data, make_skill_data,
)


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)
    inv_data = make_investigator_data(combat=3, agility=4)
    g.register_card_data(inv_data)
    loc = make_location_data()
    g.register_card_data(loc)
    g.register_card_data(CardData(
        id="sea_change_harpoon_lv0", name="Sea Change Harpoon", name_cn="沧海桑田鱼叉",
        type=CardType.ASSET, card_class=PlayerClass.NEUTRAL, cost=3,
        traits=["item", "weapon", "melee"], skill_icons={"combat": 1, "wild": 1},
    ))
    g.register_card_data(CardData(
        id="silass_net_lv0", name="Silas's Net", name_cn="西拉斯的渔网",
        type=CardType.ASSET, card_class=PlayerClass.NEUTRAL, cost=2,
        traits=["item", "tool"], skill_icons={"agility": 1, "wild": 1},
    ))
    g.register_card_data(make_enemy_data(fight=3, health=10, evade=3))
    g.register_card_data(make_skill_data(id="vicious_blow_lv0", skill_icons={"combat": 1}))
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=2)
    g.card_registry.register_class(SeaChangeHarpoon)
    g.card_registry.register_class(SilassNet)
    return g


def _equip(game, card_id, instance_id):
    inv = game.state.get_investigator("inv1")
    ci = CardInstance(
        instance_id=instance_id, card_id=card_id,
        owner_id="inv1", controller_id="inv1",
    )
    game.state.cards_in_play[instance_id] = ci
    inv.play_area.append(instance_id)
    game.card_registry.activate_card(card_id, instance_id, game.event_bus)
    return instance_id


def _spawn_enemy(game, instance_id):
    enemy = CardInstance(
        instance_id=instance_id, card_id="test_enemy",
        owner_id="scenario", controller_id="scenario",
    )
    game.state.cards_in_play[instance_id] = enemy
    game.state.get_investigator("inv1").threat_area.append(instance_id)
    return enemy


class TestSeaChangeHarpoon:
    def test_bonus_damage_with_committed_skill(self, game):
        """投入技能卡的攻击：+1战斗且+1伤害。"""
        _equip(game, "sea_change_harpoon_lv0", "harpoon_1")
        enemy = _spawn_enemy(game, "enemy_1")
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]
        inv = game.state.get_investigator("inv1")
        inv.actions_remaining = 3
        inv.hand.append("vicious_blow_lv0")

        game.action_resolver.perform_action(
            "inv1", Action.FIGHT,
            enemy_instance_id="enemy_1", weapon_instance_id="harpoon_1",
            committed_cards=["vicious_blow_lv0"],
        )
        # 战斗3 +1鱼叉 +1图标 = 5 vs 3 → 成功；伤害 1 + 1 = 2
        assert enemy.damage == 2

    def test_no_bonus_damage_without_skill(self, game):
        """未投入技能卡：只有+1战斗，无+1伤害。"""
        _equip(game, "sea_change_harpoon_lv0", "harpoon_1")
        enemy = _spawn_enemy(game, "enemy_1")
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]
        inv = game.state.get_investigator("inv1")
        inv.actions_remaining = 3

        game.action_resolver.perform_action(
            "inv1", Action.FIGHT,
            enemy_instance_id="enemy_1", weapon_instance_id="harpoon_1",
        )
        assert enemy.damage == 1

    def test_return_to_hand_returns_committed_skills(self, game):
        """选择收回：检定结束时技能卡与鱼叉均回手。"""
        _equip(game, "sea_change_harpoon_lv0", "harpoon_1")
        inv = game.state.get_investigator("inv1")

        # 模拟一次已投入技能卡的鱼叉攻击流程（ST.8 已弃置投入牌）
        game.event_bus.emit(EventContext(
            game_state=game.state, event=GameEvent.FIGHT_ACTION_INITIATED,
            investigator_id="inv1", source="harpoon_1", enemy_id="enemy_x",
        ))
        impl = game.card_registry.active_instances["harpoon_1"]
        assert impl.choose_return(game.state, "inv1") is True
        game.event_bus.emit(EventContext(
            game_state=game.state, event=GameEvent.SKILL_TEST_COMMIT,
            investigator_id="inv1", committed_cards=["vicious_blow_lv0"], amount=1,
        ))
        inv.discard.append("vicious_blow_lv0")  # ST.8 弃置
        game.event_bus.emit(EventContext(
            game_state=game.state, event=GameEvent.SKILL_TEST_ENDS,
            investigator_id="inv1", success=True,
        ))

        assert "vicious_blow_lv0" in inv.hand
        assert "vicious_blow_lv0" not in inv.discard
        assert "sea_change_harpoon_lv0" in inv.hand
        assert "harpoon_1" not in inv.play_area


class TestSilassNet:
    def test_evade_bonus_and_extra_evade(self, game):
        """投入技能卡的躲避成功：自动躲避另一个交战敌人。"""
        _equip(game, "silass_net_lv0", "net_1")
        enemy1 = _spawn_enemy(game, "enemy_1")
        enemy2 = _spawn_enemy(game, "enemy_2")
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]
        inv = game.state.get_investigator("inv1")
        inv.actions_remaining = 3
        inv.hand.append("vicious_blow_lv0")

        impl = game.card_registry.active_instances["net_1"]
        assert impl.activate(game.state, "inv1") is True

        game.action_resolver.perform_action(
            "inv1", Action.EVADE, enemy_instance_id="enemy_1",
            committed_cards=["vicious_blow_lv0"],
        )
        # 敏捷4 +1渔网 = 5 vs 3 → 成功；enemy1 被躲避
        assert enemy1.exhausted is True
        assert "enemy_1" not in inv.threat_area
        # 另一个敌人也被自动躲避
        assert enemy2.exhausted is True
        assert "enemy_2" not in inv.threat_area
        loc = game.state.locations["test_location"]
        assert "enemy_1" in loc.enemies and "enemy_2" in loc.enemies

    def test_no_extra_evade_without_skill(self, game):
        """未投入技能卡：不躲避第二个敌人。"""
        _equip(game, "silass_net_lv0", "net_1")
        enemy1 = _spawn_enemy(game, "enemy_1")
        enemy2 = _spawn_enemy(game, "enemy_2")
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]
        inv = game.state.get_investigator("inv1")
        inv.actions_remaining = 3

        impl = game.card_registry.active_instances["net_1"]
        assert impl.activate(game.state, "inv1") is True
        game.action_resolver.perform_action(
            "inv1", Action.EVADE, enemy_instance_id="enemy_1",
        )
        assert enemy1.exhausted is True
        assert enemy2.exhausted is False
        assert "enemy_2" in inv.threat_area
