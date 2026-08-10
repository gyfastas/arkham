"""Behavior tests for the guardian weapon batch:
.35 Winchester (0), .45 Thompson (0/3), Blessed Blade (0),
Brand of Cthugha (1/4), Butterfly Swords (2/5),
Cyclopean Hammer (5), Enchanted Blade (3).
"""

import pytest

from backend.cards.guardian.blessed_blade_lv0 import BlessedBlade
from backend.cards.guardian.brand_of_cthugha_lv1 import BrandOfCthughaLv1
from backend.cards.guardian.brand_of_cthugha_lv4 import BrandOfCthughaLv4
from backend.cards.guardian.butterfly_swords_lv2 import ButterflySwordsLv2
from backend.cards.guardian.butterfly_swords_lv5 import ButterflySwordsLv5
from backend.cards.guardian.cyclopean_hammer_lv5 import CyclopeanHammer
from backend.cards.guardian.enchanted_blade_lv3 import EnchantedBlade
from backend.cards.guardian.forty_five_thompson_lv0 import FortyFiveThompsonLv0
from backend.cards.guardian.forty_five_thompson_lv3 import FortyFiveThompsonLv3
from backend.cards.guardian.thirty_five_winchester_lv0 import ThirtyFiveWinchester
from backend.engine.game import Game
from backend.models.enums import (
    Action, CardType, ChaosTokenType, PlayerClass, Skill, SlotType,
)
from backend.models.state import CardData, CardInstance
from backend.tests.conftest import (
    make_asset_data, make_enemy_data, make_investigator_data, make_location_data,
)


def _game(willpower=3, intellect=3, combat=3, agility=3):
    g = Game("test")
    g.chaos_bag.seed(42)
    inv_data = make_investigator_data(
        willpower=willpower, intellect=intellect, combat=combat, agility=agility)
    g.register_card_data(inv_data)
    loc = make_location_data(connections=["loc_b"])
    g.register_card_data(loc)
    loc_b = make_location_data(id="loc_b", name="B", connections=["test_location", "loc_c"])
    g.register_card_data(loc_b)
    loc_c = make_location_data(id="loc_c", name="C", connections=["loc_b"])
    g.register_card_data(loc_c)
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)
    g.add_location("loc_b", loc_b, clues=0)
    g.add_location("loc_c", loc_c, clues=0)
    return g


def _equip(game, card_id, impl_cls, uses=None, traits=None, slots=None):
    if game.state.get_card_data(card_id) is None:
        game.register_card_data(make_asset_data(
            id=card_id, card_class=PlayerClass.GUARDIAN,
            slots=slots or [SlotType.HAND], uses=uses, traits=traits or ["weapon"],
        ))
    game.card_registry.register_class(impl_cls)
    iid = game.state.next_instance_id()
    inst = CardInstance(
        instance_id=iid, card_id=card_id, owner_id="inv1", controller_id="inv1",
        uses=dict(uses or {}),
    )
    game.state.cards_in_play[iid] = inst
    game.state.get_investigator("inv1").play_area.append(iid)
    impl = game.card_registry.activate_card(
        card_id, iid, game.event_bus, chaos_bag=game.chaos_bag)
    return impl, iid


def _enemy(game, fight=3, health=3, iid="enemy_1", keywords=None, traits=None):
    data = make_enemy_data(fight=fight, health=health, keywords=keywords or [])
    if traits:
        data.traits = traits
    game.register_card_data(data)
    inst = CardInstance(
        instance_id=iid, card_id="test_enemy",
        owner_id="scenario", controller_id="scenario",
    )
    game.state.cards_in_play[iid] = inst
    game.state.get_investigator("inv1").threat_area.append(iid)
    return inst


def _fight(game, weapon_iid=None, enemy_iid="enemy_1"):
    inv = game.state.get_investigator("inv1")
    inv.actions_remaining = 10
    game.action_resolver.perform_action(
        "inv1", Action.FIGHT,
        enemy_instance_id=enemy_iid, weapon_instance_id=weapon_iid,
    )


class TestThirtyFiveWinchester:
    def test_bonus_damage_on_zero_token(self):
        """+2战斗；揭示0标记：+2伤害（共3点），弹药-1。"""
        g = _game()
        _, wid = _equip(g, "35_winchester_lv0", ThirtyFiveWinchester,
                        uses={"ammo": 5}, traits=["item", "weapon", "firearm"])
        enemy = _enemy(g, health=10)
        g.chaos_bag.tokens = [ChaosTokenType.ZERO]
        _fight(g, wid)
        assert enemy.damage == 3  # 1 基础 + 2 标记加成
        assert g.state.get_card_instance(wid).uses["ammo"] == 4

    def test_no_bonus_on_minus_token(self):
        """揭示-1标记：无加成，仅基础1伤害。"""
        g = _game()
        _, wid = _equip(g, "35_winchester_lv0", ThirtyFiveWinchester,
                        uses={"ammo": 5}, traits=["item", "weapon", "firearm"])
        enemy = _enemy(g, health=10)
        g.chaos_bag.tokens = [ChaosTokenType.MINUS_1]
        # 战斗3+2-1=4 vs 3 → 成功
        _fight(g, wid)
        assert enemy.damage == 1

    def test_no_ammo_cancels_attack(self):
        """无弹药：攻击被取消，敌人不受伤害。"""
        g = _game()
        _, wid = _equip(g, "35_winchester_lv0", ThirtyFiveWinchester,
                        uses={"ammo": 0}, traits=["item", "weapon", "firearm"])
        enemy = _enemy(g, health=10)
        g.chaos_bag.tokens = [ChaosTokenType.PLUS_1]
        _fight(g, wid)
        assert enemy.damage == 0


class TestFortyFiveThompson:
    def test_lv0_bonus_and_damage(self):
        """lv0：+2战斗、+1伤害（共2点），弹药-1。"""
        g = _game()
        _, wid = _equip(g, "45_thompson_lv0", FortyFiveThompsonLv0,
                        uses={"ammo": 5}, traits=["item", "weapon", "firearm"])
        enemy = _enemy(g, fight=5, health=10)
        g.chaos_bag.tokens = [ChaosTokenType.ZERO]
        # 战斗3+2=5 vs 5 → 成功
        _fight(g, wid)
        assert enemy.damage == 2
        assert g.state.get_card_instance(wid).uses["ammo"] == 4

    def test_lv3_ammo_becomes_resources(self):
        """lv3：花费的弹药转为资源（资源+1）。"""
        g = _game()
        _, wid = _equip(g, "45_thompson_lv3", FortyFiveThompsonLv3,
                        uses={"ammo": 5}, traits=["item", "weapon", "firearm"])
        enemy = _enemy(g, health=10)
        inv = g.state.get_investigator("inv1")
        inv.resources = 5
        g.chaos_bag.tokens = [ChaosTokenType.ZERO]
        _fight(g, wid)
        assert enemy.damage == 2
        assert g.state.get_card_instance(wid).uses["ammo"] == 4
        assert inv.resources == 6  # 弹药转化为1资源


class TestBlessedBlade:
    def test_bless_token_bonus_damage(self):
        """揭示祝福标记：+1战斗，+1伤害（共2点）。"""
        g = _game()
        _, wid = _equip(g, "blessed_blade_lv0", BlessedBlade,
                        traits=["item", "weapon", "melee", "blessed"])
        enemy = _enemy(g, health=10)
        g.chaos_bag.tokens = [ChaosTokenType.BLESS]
        _fight(g, wid)
        # 祝福+2：3+1+2=6 vs 3 成功；伤害 1+1
        assert enemy.damage == 2

    def test_normal_token_no_bonus(self):
        """普通标记：仅基础1伤害（+1战斗仍生效，用 fight4 敌人验证）。"""
        g = _game()
        _, wid = _equip(g, "blessed_blade_lv0", BlessedBlade,
                        traits=["item", "weapon", "melee", "blessed"])
        enemy = _enemy(g, fight=4, health=10)
        g.chaos_bag.tokens = [ChaosTokenType.ZERO]
        # 战斗3+1=4 vs 4 → 成功
        _fight(g, wid)
        assert enemy.damage == 1

    def test_add_bless_exhausts_and_blocks_fight(self):
        """横置加祝福：袋中+1祝福标记；横置后不能以本卡攻击。"""
        g = _game()
        impl, wid = _equip(g, "blessed_blade_lv0", BlessedBlade,
                           traits=["item", "weapon", "melee", "blessed"])
        enemy = _enemy(g, health=10)
        before = g.chaos_bag.tokens.count(ChaosTokenType.BLESS)
        assert impl.activate_add_bless(g.state, "inv1") is True
        assert g.chaos_bag.tokens.count(ChaosTokenType.BLESS) == before + 1
        assert g.state.get_card_instance(wid).exhausted is True
        g.chaos_bag.tokens = [ChaosTokenType.ZERO]
        _fight(g, wid)
        assert enemy.damage == 0  # 已横置，攻击被取消


class TestBrandOfCthugha:
    def test_lv1_willpower_substitute_and_charge_damage(self):
        """lv1：意志(4)代替战斗(2)，+1技能值；成功自动花2充能造成2伤害。"""
        g = _game(willpower=4, combat=2)
        _, wid = _equip(g, "brand_of_cthugha_lv1", BrandOfCthughaLv1,
                        uses={"chargess": 6},  # 数据复数化键容错
                        traits=["spell"], slots=[SlotType.ARCANE])
        enemy = _enemy(g, health=10)
        impl = g.card_registry.active_instances[wid]
        assert impl.activate(g.state, "inv1") is True
        g.chaos_bag.tokens = [ChaosTokenType.ZERO]
        # 意志4+1=5 vs 3 → 成功
        _fight(g, wid)
        assert enemy.damage == 2
        assert g.state.get_card_instance(wid).uses["chargess"] == 4

    def test_lv1_exact_success_loses_action(self):
        """lv1：成功超出0点，失去1个行动。"""
        g = _game(willpower=4, combat=2)
        _, wid = _equip(g, "brand_of_cthugha_lv1", BrandOfCthughaLv1,
                        uses={"charges": 6}, traits=["spell"], slots=[SlotType.ARCANE])
        _enemy(g, fight=5, health=10)
        impl = g.card_registry.active_instances[wid]
        impl.activate(g.state, "inv1")
        inv = g.state.get_investigator("inv1")
        inv.actions_remaining = 3
        g.chaos_bag.tokens = [ChaosTokenType.ZERO]
        # 5 vs 5 → 恰好成功
        g.action_resolver.perform_action(
            "inv1", Action.FIGHT, enemy_instance_id="enemy_1", weapon_instance_id=wid)
        assert inv.actions_remaining == 1  # 3 - 1(战斗) - 1(代价)

    def test_lv4_spends_3_charges(self):
        """lv4：+2技能值；成功自动花3充能造成3伤害。"""
        g = _game(willpower=4, combat=2)
        _, wid = _equip(g, "brand_of_cthugha_lv4", BrandOfCthughaLv4,
                        uses={"chargess": 9}, traits=["spell"], slots=[SlotType.ARCANE])
        enemy = _enemy(g, health=10)
        impl = g.card_registry.active_instances[wid]
        impl.activate(g.state, "inv1")
        g.chaos_bag.tokens = [ChaosTokenType.ZERO]
        # 意志4+2=6 vs 3 → 成功
        _fight(g, wid)
        assert enemy.damage == 3
        assert g.state.get_card_instance(wid).uses["chargess"] == 6

    def test_lv4_exact_success_loses_2_actions(self):
        """lv4：成功超出0点，失去2个行动。"""
        g = _game(willpower=4, combat=2)
        _, wid = _equip(g, "brand_of_cthugha_lv4", BrandOfCthughaLv4,
                        uses={"charges": 9}, traits=["spell"], slots=[SlotType.ARCANE])
        _enemy(g, fight=6, health=10)
        impl = g.card_registry.active_instances[wid]
        impl.activate(g.state, "inv1")
        inv = g.state.get_investigator("inv1")
        inv.actions_remaining = 3
        g.chaos_bag.tokens = [ChaosTokenType.ZERO]
        # 6 vs 6 → 恰好成功
        g.action_resolver.perform_action(
            "inv1", Action.FIGHT, enemy_instance_id="enemy_1", weapon_instance_id=wid)
        assert inv.actions_remaining == 0  # 3 - 1(战斗) - 2(代价)


class TestButterflySwords:
    def test_lv2_followup_attack(self):
        """lv2：第一次攻击+1战斗；横置追加攻击加敏捷且+1伤害。"""
        g = _game(combat=3, agility=4)
        _, wid = _equip(g, "butterfly_swords_lv2", ButterflySwordsLv2,
                        traits=["item", "weapon", "melee"],
                        slots=[SlotType.HAND, SlotType.HAND])
        enemy = _enemy(g, fight=4, health=10)
        g.chaos_bag.tokens = [ChaosTokenType.ZERO]
        _fight(g, wid)
        # 战斗3+1=4 vs 4 → 成功，基础1伤害
        assert enemy.damage == 1

        impl = g.card_registry.active_instances[wid]
        assert impl.activate_fight_again(g.state, "inv1", "enemy_1") is True
        assert g.state.get_card_instance(wid).exhausted is True
        _fight(g, wid)
        # 追加：战斗3+1+敏捷4=8 vs 4 → 成功，1+1=2伤害
        assert enemy.damage == 3

    def test_lv2_followup_requires_first_attack(self):
        """lv2：未先攻击则不能追加。"""
        g = _game()
        _, wid = _equip(g, "butterfly_swords_lv2", ButterflySwordsLv2,
                        traits=["item", "weapon", "melee"],
                        slots=[SlotType.HAND, SlotType.HAND])
        _enemy(g)
        impl = g.card_registry.active_instances[wid]
        assert impl.activate_fight_again(g.state, "inv1", "enemy_1") is False

    def test_lv5_double_success_exhausts_for_bonus(self):
        """lv5：+2战斗；追加不预先横置；两次都成功则自动横置+1伤害。"""
        g = _game(combat=3, agility=4)
        _, wid = _equip(g, "butterfly_swords_lv5", ButterflySwordsLv5,
                        traits=["item", "weapon", "melee"],
                        slots=[SlotType.HAND, SlotType.HAND])
        enemy = _enemy(g, health=10)
        g.chaos_bag.tokens = [ChaosTokenType.ZERO]
        _fight(g, wid)
        assert enemy.damage == 1  # 第一次基础1
        assert g.state.get_card_instance(wid).exhausted is False

        impl = g.card_registry.active_instances[wid]
        assert impl.activate_fight_again(g.state, "inv1", "enemy_1") is True
        assert g.state.get_card_instance(wid).exhausted is False  # 不预先横置
        _fight(g, wid)
        # 追加：3+2+4=9 vs 3 → 成功；双成功自动横置 +1伤害 → 1+1=2
        assert enemy.damage == 3
        assert g.state.get_card_instance(wid).exhausted is True

    def test_lv5_no_bonus_if_first_failed(self):
        """lv5：第一次失败则追加成功也不横置、无+1伤害。"""
        g = _game(combat=3, agility=4)
        _, wid = _equip(g, "butterfly_swords_lv5", ButterflySwordsLv5,
                        traits=["item", "weapon", "melee"],
                        slots=[SlotType.HAND, SlotType.HAND])
        enemy = _enemy(g, health=10)
        g.chaos_bag.tokens = [ChaosTokenType.AUTO_FAIL]
        _fight(g, wid)
        assert enemy.damage == 0  # 第一次失败

        impl = g.card_registry.active_instances[wid]
        assert impl.activate_fight_again(g.state, "inv1", "enemy_1") is True
        g.chaos_bag.tokens = [ChaosTokenType.ZERO]
        _fight(g, wid)
        assert enemy.damage == 1  # 追加成功但无加成
        assert g.state.get_card_instance(wid).exhausted is False


class TestCyclopeanHammer:
    def test_big_success_damage_and_push_two_steps(self):
        """意志加入技能值；超出≥3：+2伤害，可击退至多2个地点。"""
        g = _game(willpower=4, combat=3)
        impl, wid = _equip(g, "cyclopean_hammer_lv5", CyclopeanHammer,
                           traits=["item", "relic", "weapon", "melee"],
                           slots=[SlotType.HAND, SlotType.HAND])
        enemy = _enemy(g, fight=3, health=10)
        g.chaos_bag.tokens = [ChaosTokenType.ZERO]
        # 战斗3+意志4=7 vs 3 → 超4 → +2伤害
        _fight(g, wid)
        assert enemy.damage == 3

        inv = g.state.get_investigator("inv1")
        assert impl.move_enemy_away(g.state, "inv1") is True
        assert "enemy_1" not in inv.threat_area
        assert "enemy_1" in g.state.get_location("loc_b").enemies
        # 第二步：B→C（不能回到你所在地点）
        assert impl.move_enemy_away(g.state, "inv1") is True
        assert "enemy_1" in g.state.get_location("loc_c").enemies
        # 步数用尽
        assert impl.move_enemy_away(g.state, "inv1") is False

    def test_small_success_single_push(self):
        """超出<3：+1伤害，仅可击退1个地点。"""
        g = _game(willpower=4, combat=3)
        impl, wid = _equip(g, "cyclopean_hammer_lv5", CyclopeanHammer,
                           traits=["item", "relic", "weapon", "melee"],
                           slots=[SlotType.HAND, SlotType.HAND])
        enemy = _enemy(g, fight=5, health=10)
        g.chaos_bag.tokens = [ChaosTokenType.ZERO]
        # 7 vs 5 → 超2 → +1伤害
        _fight(g, wid)
        assert enemy.damage == 2
        assert impl.move_enemy_away(g.state, "inv1") is True
        assert impl.move_enemy_away(g.state, "inv1") is False

    def test_elite_enemy_cannot_be_pushed(self):
        """精英敌人：伤害照常，但不能被移动。"""
        g = _game(willpower=4, combat=3)
        impl, wid = _equip(g, "cyclopean_hammer_lv5", CyclopeanHammer,
                           traits=["item", "relic", "weapon", "melee"],
                           slots=[SlotType.HAND, SlotType.HAND])
        enemy = _enemy(g, fight=3, health=10, keywords=["elite"])
        g.chaos_bag.tokens = [ChaosTokenType.ZERO]
        _fight(g, wid)
        assert enemy.damage == 3
        assert impl.move_enemy_away(g.state, "inv1") is False


class TestEnchantedBlade:
    def test_empower_spends_charge_for_bonus(self):
        """+2战斗；成功自动花1充能：+1伤害。"""
        g = _game()
        _, wid = _equip(g, "enchanted_blade_lv3", EnchantedBlade,
                        uses={"chargess": 3},  # 数据复数化键容错
                        traits=["item", "relic", "weapon", "melee"])
        enemy = _enemy(g, health=10)
        g.chaos_bag.tokens = [ChaosTokenType.ZERO]
        _fight(g, wid)
        assert enemy.damage == 2
        assert g.state.get_card_instance(wid).uses["chargess"] == 2

    def test_empowered_defeat_draws_and_heals(self):
        """强化的攻击击败敌人：抽1张牌并治愈1点恐惧。"""
        g = _game()
        _, wid = _equip(g, "enchanted_blade_lv3", EnchantedBlade,
                        uses={"charges": 3},
                        traits=["item", "relic", "weapon", "melee"])
        enemy = _enemy(g, health=2)  # 2伤害即击败
        inv = g.state.get_investigator("inv1")
        inv.deck = ["some_card"]
        inv.horror = 1
        g.chaos_bag.tokens = [ChaosTokenType.ZERO]
        _fight(g, wid)
        assert "enemy_1" not in g.state.cards_in_play  # 被击败
        assert "some_card" in inv.hand
        assert inv.horror == 0

    def test_no_charge_no_empower(self):
        """无充能：不强化，仅基础1伤害。"""
        g = _game()
        _, wid = _equip(g, "enchanted_blade_lv3", EnchantedBlade,
                        uses={"charges": 0},
                        traits=["item", "relic", "weapon", "melee"])
        enemy = _enemy(g, health=10)
        g.chaos_bag.tokens = [ChaosTokenType.ZERO]
        _fight(g, wid)
        assert enemy.damage == 1
