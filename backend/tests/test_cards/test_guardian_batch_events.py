"""Behavior tests for the guardian event batch:
Blood Eclipse (3), Custom Ammunition (3), Delay the Inevitable (0),
Dodge (2), Enchant Weapon (3), Fang of Tyr'thrha (4), First Watch (0).
"""

import pytest

from backend.cards.guardian.blood_eclipse_lv3 import BloodEclipse
from backend.cards.guardian.custom_ammunition_lv3 import CustomAmmunition
from backend.cards.guardian.delay_the_inevitable_lv0 import DelayTheInevitable
from backend.cards.guardian.dodge_lv2 import DodgeLv2
from backend.cards.guardian.enchant_weapon_lv3 import EnchantWeapon
from backend.cards.guardian.fang_of_tyrthrha_lv4 import FangOfTyrthrha
from backend.cards.guardian.first_watch_lv0 import FirstWatch
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import (
    Action, CardType, ChaosTokenType, GameEvent, PlayerClass, Skill, SlotType,
)
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_asset_data, make_enemy_data, make_event_data, make_investigator_data,
    make_location_data,
)


def _game(willpower=3, intellect=3, combat=3, agility=3, clues=0):
    g = Game("test")
    g.chaos_bag.seed(42)
    inv_data = make_investigator_data(
        willpower=willpower, intellect=intellect, combat=combat, agility=agility)
    g.register_card_data(inv_data)
    loc = make_location_data(clue_value=clues)
    g.register_card_data(loc)
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=clues)
    return g


def _register_event(game, card_id, impl_cls, cost=0, fast=False):
    game.register_card_data(make_event_data(
        id=card_id, cost=cost, card_class=PlayerClass.GUARDIAN, fast=fast))
    game.card_registry.register_class(impl_cls)


def _play_event(game, card_id, inv_id="inv1"):
    inv = game.state.get_investigator(inv_id)
    if card_id not in inv.hand:
        inv.hand.append(card_id)
    inv.actions_remaining = 10
    ok = game.action_resolver.perform_action(inv_id, Action.PLAY, card_id=card_id)
    assert ok


def _enemy(game, fight=3, health=3, iid="enemy_1", keywords=None, traits=None,
           engaged=True, location_id="test_location"):
    data = make_enemy_data(fight=fight, health=health, keywords=keywords or [])
    if traits:
        data.traits = traits
    game.register_card_data(data)
    inst = CardInstance(
        instance_id=iid, card_id="test_enemy",
        owner_id="scenario", controller_id="scenario",
    )
    game.state.cards_in_play[iid] = inst
    if engaged:
        game.state.get_investigator("inv1").threat_area.append(iid)
    else:
        game.state.get_location(location_id).enemies.append(iid)
    return inst


def _weapon(game, iid="gun_1", card_id="test_gun", traits=None, uses=None):
    if game.state.get_card_data(card_id) is None:
        game.register_card_data(make_asset_data(
            id=card_id, card_class=PlayerClass.GUARDIAN,
            traits=traits or ["item", "weapon", "firearm"],
            slots=[SlotType.HAND], uses=uses))
    inst = CardInstance(
        instance_id=iid, card_id=card_id, owner_id="inv1", controller_id="inv1",
        uses=dict(uses or {}))
    game.state.cards_in_play[iid] = inst
    game.state.get_investigator("inv1").play_area.append(iid)
    return inst


def _fight(game, weapon_iid=None, enemy_iid="enemy_1"):
    inv = game.state.get_investigator("inv1")
    inv.actions_remaining = 10
    game.action_resolver.perform_action(
        "inv1", Action.FIGHT,
        enemy_instance_id=enemy_iid, weapon_instance_id=weapon_iid,
    )


def _emit(game, event, **kwargs):
    ctx = EventContext(game_state=game.state, event=event, **kwargs)
    game.event_bus.emit(ctx)
    return ctx


class TestBloodEclipse:
    def test_power_from_self_damage(self):
        """额外费用自动受3伤：攻击以意志代替战斗，+3意志/+3伤害。"""
        g = _game(willpower=4, combat=2)
        _register_event(g, "blood_eclipse_lv3", BloodEclipse, cost=1)
        # 敌人不交战（避免打出事件时的趁乱攻击干扰伤害断言）
        enemy = _enemy(g, health=10, engaged=False)
        inv = g.state.get_investigator("inv1")
        _play_event(g, "blood_eclipse_lv3")
        assert inv.damage == 3
        g.chaos_bag.tokens = [ChaosTokenType.ZERO]
        _fight(g)  # 徒手（事件攻击）
        # 战斗2 → 意志4+3=7 vs 3 → 成功；伤害 1+3=4
        assert enemy.damage == 4

    def test_self_damage_never_lethal(self):
        """自动受伤不致败：剩余1生命时仅受1点。"""
        g = _game(willpower=4, combat=2)
        _register_event(g, "blood_eclipse_lv3", BloodEclipse, cost=1)
        enemy = _enemy(g, health=10, engaged=False)
        inv = g.state.get_investigator("inv1")
        inv.damage = 5  # 生命7 → 安全余量1
        _play_event(g, "blood_eclipse_lv3")
        assert inv.damage == 6
        g.chaos_bag.tokens = [ChaosTokenType.ZERO]
        _fight(g)
        assert enemy.damage == 2  # 1 + 1


class TestCustomAmmunition:
    def test_attach_reload_and_monster_bonus(self):
        """打出：枪械+2弹药；该枪对 Monster 敌人+1伤害。"""
        g = _game()
        _register_event(g, "custom_ammunition_lv3", CustomAmmunition,
                        cost=3, fast=True)
        gun = _weapon(g, uses={"ammo": 4})
        _enemy(g, health=10, traits=["monster"])
        _play_event(g, "custom_ammunition_lv3")
        assert gun.uses["ammo"] == 6
        assert "gun_1" in g.state.scenario.vars["custom_ammunition"]

        enemy = g.state.get_card_instance("enemy_1")
        g.chaos_bag.tokens = [ChaosTokenType.ZERO]
        _fight(g, "gun_1")
        assert enemy.damage == 2  # 1 基础 + 1 定制弹药

    def test_no_bonus_vs_non_monster(self):
        """对非 Monster 敌人无加成。"""
        g = _game()
        _register_event(g, "custom_ammunition_lv3", CustomAmmunition,
                        cost=3, fast=True)
        _weapon(g, uses={"ammo": 4})
        _enemy(g, health=10, traits=["humanoid"])
        _play_event(g, "custom_ammunition_lv3")
        enemy = g.state.get_card_instance("enemy_1")
        g.chaos_bag.tokens = [ChaosTokenType.ZERO]
        _fight(g, "gun_1")
        assert enemy.damage == 1


class TestDelayTheInevitable:
    def test_cancels_first_damage(self):
        """被造成伤害时：弃置并取消全部伤害；之后正常受伤。"""
        g = _game()
        _register_event(g, "delay_the_inevitable_lv0", DelayTheInevitable,
                        cost=2, fast=True)
        _play_event(g, "delay_the_inevitable_lv0")
        inv = g.state.get_investigator("inv1")
        g.damage_engine.deal_damage("inv1", damage=3)
        assert inv.damage == 0
        assert "delay_the_inevitable" not in g.state.scenario.vars
        g.damage_engine.deal_damage("inv1", damage=2)
        assert inv.damage == 2

    def test_cancels_horror(self):
        """恐惧同样被取消。"""
        g = _game()
        _register_event(g, "delay_the_inevitable_lv0", DelayTheInevitable,
                        cost=2, fast=True)
        _play_event(g, "delay_the_inevitable_lv0")
        inv = g.state.get_investigator("inv1")
        g.damage_engine.deal_damage("inv1", horror=2)
        assert inv.horror == 0

    def test_mythos_upkeep_paid(self):
        """神话阶段结束：资源足够则自动支付2资源保留。"""
        g = _game()
        _register_event(g, "delay_the_inevitable_lv0", DelayTheInevitable,
                        cost=2, fast=True)
        _play_event(g, "delay_the_inevitable_lv0")
        inv = g.state.get_investigator("inv1")
        inv.resources = 5
        _emit(g, GameEvent.MYTHOS_PHASE_ENDS)
        assert inv.resources == 3
        assert "delay_the_inevitable" in g.state.scenario.vars

    def test_mythos_upkeep_unpaid_discards(self):
        """神话阶段结束：资源不足则弃置。"""
        g = _game()
        _register_event(g, "delay_the_inevitable_lv0", DelayTheInevitable,
                        cost=2, fast=True)
        _play_event(g, "delay_the_inevitable_lv0")
        inv = g.state.get_investigator("inv1")
        inv.resources = 1
        _emit(g, GameEvent.MYTHOS_PHASE_ENDS)
        assert inv.resources == 1
        assert "delay_the_inevitable" not in g.state.scenario.vars


class TestDodgeLv2:
    def _hand_dodge(self, g):
        g.card_registry.register_class(DodgeLv2)
        g.register_card_data(make_event_data(
            id="dodge_lv2", cost=0, card_class=PlayerClass.GUARDIAN, fast=True))
        impl = g.card_registry.activate_card(
            "dodge_lv2", "dodge_tmp", g.event_bus, chaos_bag=g.chaos_bag)
        inv = g.state.get_investigator("inv1")
        inv.hand = ["dodge_lv2"]
        return impl, inv

    def test_cancel_and_counter_damage(self):
        """敌人攻击时自动打出：取消攻击；敏捷检定成功反击1伤害。"""
        g = _game(agility=3)
        impl, inv = self._hand_dodge(g)
        enemy = _enemy(g, health=5)
        g.chaos_bag.tokens = [ChaosTokenType.ZERO]
        ctx = _emit(g, GameEvent.ENEMY_ATTACKS, investigator_id="inv1",
                    enemy_id="enemy_1")
        assert ctx.cancelled is True
        assert "dodge_lv2" in inv.discard
        assert "dodge_lv2" not in inv.hand
        assert enemy.damage == 1

    def test_failed_test_no_counter(self):
        """敏捷检定失败：攻击仍取消，但无反击伤害。"""
        g = _game(agility=3)
        impl, inv = self._hand_dodge(g)
        enemy = _enemy(g, health=5)
        g.chaos_bag.tokens = [ChaosTokenType.AUTO_FAIL]
        ctx = _emit(g, GameEvent.ENEMY_ATTACKS, investigator_id="inv1",
                    enemy_id="enemy_1")
        assert ctx.cancelled is True
        assert enemy.damage == 0


class TestEnchantWeapon:
    def _setup(self, g):
        _register_event(g, "enchant_weapon_lv3", EnchantWeapon, cost=3)
        _weapon(g, iid="blade_1", card_id="test_blade",
                traits=["item", "weapon", "melee"])
        _enemy(g, health=20)
        _play_event(g, "enchant_weapon_lv3")

    def test_attach_and_empower_attack(self):
        """叠加到武器；用该武器攻击时自动横置：+拥有者意志、+1伤害。"""
        g = _game(willpower=4, combat=3)
        self._setup(g)
        assert "blade_1" in g.state.scenario.vars["enchant_weapon"]
        enemy = g.state.get_card_instance("enemy_1")
        g.chaos_bag.tokens = [ChaosTokenType.ZERO]
        _fight(g, "blade_1")
        # 战斗3+意志4=7 vs 3 → 成功；伤害 1+1=2
        assert enemy.damage == 2
        record = g.state.scenario.vars["enchant_weapon"]["blade_1"]
        assert record["exhausted"] is True

    def test_exhausted_no_bonus_until_upkeep(self):
        """横置后无加成； upkeep 准备后恢复。"""
        g = _game(willpower=4, combat=3)
        self._setup(g)
        enemy = g.state.get_card_instance("enemy_1")
        g.chaos_bag.tokens = [ChaosTokenType.ZERO]
        _fight(g, "blade_1")
        assert enemy.damage == 2
        _fight(g, "blade_1")
        assert enemy.damage == 3  # 第二次无加成（+1）
        _emit(g, GameEvent.UPKEEP_PHASE_BEGINS)
        _fight(g, "blade_1")
        assert enemy.damage == 5  # 恢复后再次 +2


class TestFangOfTyrthrha:
    def test_move_and_powered_attack(self):
        """选择已揭示地点的敌人：自动移动到其地点；+敏捷、+3伤害。"""
        g = _game(combat=3, agility=4)
        _register_event(g, "fang_of_tyrthrha_lv4", FangOfTyrthrha, cost=3)
        loc_b = make_location_data(id="loc_b", name="B")
        g.register_card_data(loc_b)
        g.add_location("loc_b", loc_b, clues=0)
        g.state.get_location("loc_b").revealed = True
        enemy = _enemy(g, health=10, engaged=False, location_id="loc_b")
        inv = g.state.get_investigator("inv1")

        _play_event(g, "fang_of_tyrthrha_lv4")
        assert inv.location_id == "loc_b"  # 自动移动到敌人所在地点

        g.chaos_bag.tokens = [ChaosTokenType.ZERO]
        _fight(g, enemy_iid="enemy_1")
        # 战斗3+敏捷4=7 vs 3 → 成功；伤害 1+3=4
        assert enemy.damage == 4

    def test_fizzles_without_enemy(self):
        """没有可选敌人时不武装。"""
        g = _game()
        _register_event(g, "fang_of_tyrthrha_lv4", FangOfTyrthrha, cost=3)
        _play_event(g, "fang_of_tyrthrha_lv4")
        # 无敌人：仅记录 fizzle，无异常
        assert not g.state.scenario.vars.get("fang_of_tyrthrha_lv4")


class TestFirstWatch:
    def _setup(self, g):
        _register_event(g, "first_watch_lv0", FirstWatch, cost=1, fast=True)
        inv_data2 = make_investigator_data(id="inv2", name="I2")
        g.register_card_data(inv_data2)
        g.add_investigator("inv2", inv_data2, starting_location="test_location")
        g.state.scenario.encounter_deck = ["c_one", "c_two", "c_three"]
        drawn = []
        g.event_bus.register(
            GameEvent.ENCOUNTER_CARD_DRAWN,
            lambda ctx: drawn.append((ctx.investigator_id, ctx.extra["card_id"])),
        )
        return drawn

    def test_look_and_deal(self):
        """查看顶X张并分配：持有者先分，每人1张，替代标记置位。"""
        g = _game()
        drawn = self._setup(g)
        _play_event(g, "first_watch_lv0")
        sc = g.state.scenario
        assert sc.encounter_deck == ["c_three"]
        assert sorted(sc.encounter_discard) == ["c_one", "c_two"]
        assert sc.vars["encounter_draw_step_replaced"] is True
        # 持有者 inv1 先分：inv1→c_one, inv2→c_two
        assert drawn == [("inv1", "c_one"), ("inv2", "c_two")]

    def test_holder_dealt_first(self):
        """持有者为 inv2 时从 inv2 开始分配。"""
        g = _game()
        drawn = self._setup(g)
        _play_event(g, "first_watch_lv0", inv_id="inv2")
        assert drawn == [("inv2", "c_one"), ("inv1", "c_two")]
