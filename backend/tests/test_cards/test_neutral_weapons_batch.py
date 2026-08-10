"""Tests for neutral weapons/asset combat batch:
Timeworn Brand (lv5) / Tony's .38 Long Colt / Trusty Bullwhip /
Twilight Blade / Trench Coat.
"""

import pytest

from backend.cards.neutral.timeworn_brand_lv5 import TimewornBrand
from backend.cards.neutral.tonys_38_long_colt_lv0 import Tonys38LongColt
from backend.cards.neutral.trench_coat_lv0 import TrenchCoat
from backend.cards.neutral.trusty_bullwhip_lv0 import TrustyBullwhip
from backend.cards.neutral.twilight_blade_lv0 import TwilightBlade
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import (
    Action, CardType, ChaosTokenType, GameEvent, PlayerClass, Skill, SlotType,
)
from backend.models.state import CardData, CardInstance
from backend.tests.conftest import (
    make_enemy_data, make_investigator_data, make_location_data,
)


def _make_game(impl_classes=(), willpower=3, intellect=3, combat=3, agility=3):
    g = Game("test")
    g.chaos_bag.seed(42)
    inv_data = make_investigator_data(
        id="inv1", willpower=willpower, intellect=intellect,
        combat=combat, agility=agility)
    g.register_card_data(inv_data)
    loc = make_location_data()
    g.register_card_data(loc)
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=2)
    for cls in impl_classes:
        g.card_registry.register_class(cls)
    return g


def _register_asset_data(game, card_id, slots=None, uses=None, traits=None):
    game.register_card_data(CardData(
        id=card_id, name=card_id, name_cn=card_id,
        type=CardType.ASSET, card_class=PlayerClass.NEUTRAL, cost=2,
        slots=slots or [], uses=uses, traits=traits or [],
    ))


def _equip(game, card_id, uses=None):
    """Put an asset instance directly into inv1's play area + activate impl."""
    inv = game.state.get_investigator("inv1")
    inst_id = game.state.next_instance_id()
    ci = CardInstance(
        instance_id=inst_id, card_id=card_id,
        owner_id="inv1", controller_id="inv1",
    )
    if uses:
        ci.uses = dict(uses)
    game.state.cards_in_play[inst_id] = ci
    inv.play_area.append(inst_id)
    game.card_registry.activate_card(card_id, inst_id, game.event_bus)
    return inst_id


def _spawn_enemy(game, instance_id="enemy_1", fight=3, health=3, evade=3,
                 bounties=0, traits=None, card_id="test_enemy"):
    if game.state.get_card_data(card_id) is None:
        game.register_card_data(make_enemy_data(
            id=card_id, fight=fight, health=health, evade=evade))
    if traits is not None:
        game.state.card_database[card_id].traits = traits
    enemy = CardInstance(
        instance_id=instance_id, card_id=card_id,
        owner_id="scenario", controller_id="scenario",
    )
    if bounties:
        enemy.uses["bounty"] = bounties
    game.state.cards_in_play[instance_id] = enemy
    game.state.get_investigator("inv1").threat_area.append(instance_id)
    return enemy


def _fight(game, weapon_id, enemy_id="enemy_1"):
    inv = game.state.get_investigator("inv1")
    inv.actions_remaining = 3
    return game.action_resolver.perform_action(
        "inv1", Action.FIGHT,
        enemy_instance_id=enemy_id, weapon_instance_id=weapon_id)


class TestTimewornBrand:
    def _setup(self, **skills):
        game = _make_game([TimewornBrand], **skills)
        _register_asset_data(game, "timeworn_brand_lv5", slots=[SlotType.HAND])
        return game

    def test_ready_fight_bonus(self):
        """模式一（就绪）：+2战斗、+1伤害，且不横置。"""
        game = self._setup(combat=3)
        brand = _equip(game, "timeworn_brand_lv5")
        enemy = _spawn_enemy(game, fight=3, health=5)
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]

        impl = game.card_registry.active_instances[brand]
        assert impl.activate_fight(game.state, "inv1") is True
        _fight(game, brand)

        assert enemy.damage == 2  # 1基础 +1
        assert game.state.get_card_instance(brand).exhausted is False

    def test_exhaust_fight_adds_willpower_and_elite_draw(self):
        """模式二（横置）：+意志、+3伤害；击败精英抽3张（每场游戏限一次）。"""
        game = self._setup(combat=1, willpower=4)
        brand = _equip(game, "timeworn_brand_lv5")
        enemy = _spawn_enemy(game, fight=4, health=4, traits=["elite"])
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]
        inv = game.state.get_investigator("inv1")
        inv.deck = ["c1", "c2", "c3", "c4"]

        impl = game.card_registry.active_instances[brand]
        assert impl.activate_fight_exhaust(game.state, "inv1") is True
        assert game.state.get_card_instance(brand).exhausted is True
        _fight(game, brand)

        # 战斗1 + 意志4 = 5 >= 4 成功；1基础 +3 = 4伤害击败精英
        assert game.state.get_card_instance("enemy_1") is None
        assert len(inv.hand) == 3
        assert inv.deck == ["c4"]

        # 每场游戏限一次：第二次击败精英不再抽牌
        game.state.get_card_instance(brand).exhausted = False
        _spawn_enemy(game, "enemy_2", fight=4, health=4, traits=["elite"])
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]
        assert impl.activate_fight_exhaust(game.state, "inv1") is True
        _fight(game, brand, "enemy_2")
        assert game.state.get_card_instance("enemy_2") is None
        assert len(inv.hand) == 3  # 未再抽牌

    def test_exhaust_fight_non_elite_no_draw(self):
        """模式二击败非精英敌人：不抽牌。"""
        game = self._setup(combat=1, willpower=4)
        brand = _equip(game, "timeworn_brand_lv5")
        _spawn_enemy(game, fight=4, health=4)  # 无 elite 特质
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]
        inv = game.state.get_investigator("inv1")
        inv.deck = ["c1", "c2", "c3"]

        impl = game.card_registry.active_instances[brand]
        impl.activate_fight_exhaust(game.state, "inv1")
        _fight(game, brand)

        assert game.state.get_card_instance("enemy_1") is None
        assert inv.hand == []

    def test_exhausted_brand_cannot_activate(self):
        game = self._setup()
        brand = _equip(game, "timeworn_brand_lv5")
        game.state.get_card_instance(brand).exhausted = True
        impl = game.card_registry.active_instances[brand]
        assert impl.activate_fight(game.state, "inv1") is False
        assert impl.activate_fight_exhaust(game.state, "inv1") is False


class TestTonys38LongColt:
    def _setup(self, **skills):
        game = _make_game([Tonys38LongColt], **skills)
        _register_asset_data(
            game, "tonys_38_long_colt_lv0",
            slots=[SlotType.HAND], uses={"ammo": 3},
            traits=["item", "weapon", "firearm"])
        return game

    def test_reaction_plays_second_copy_free(self):
        """打出后反应：免费打出手中第二把（3弹药、占手槽）。"""
        game = self._setup()
        colt1 = _equip(game, "tonys_38_long_colt_lv0", uses={"ammo": 3})
        inv = game.state.get_investigator("inv1")
        inv.hand.append("tonys_38_long_colt_lv0")

        ctx = EventContext(
            game_state=game.state, event=GameEvent.CARD_ENTERS_PLAY,
            investigator_id="inv1", target=colt1,
            extra={"card_id": "tonys_38_long_colt_lv0"})
        game.event_bus.emit(ctx)

        assert "tonys_38_long_colt_lv0" not in inv.hand
        assert len(inv.play_area) == 2
        second_id = next(i for i in inv.play_area if i != colt1)
        second = game.state.get_card_instance(second_id)
        assert second.card_id == "tonys_38_long_colt_lv0"
        assert second.uses.get("ammo") == 3
        assert inv.resources == 5  # 免费，未扣资源

    def test_fight_bounty_bonus_and_ammo(self):
        """攻击带2赏金的敌人：+2战斗、+1伤害，消耗1弹药。"""
        game = self._setup(combat=3)
        colt = _equip(game, "tonys_38_long_colt_lv0", uses={"ammo": 3})
        enemy = _spawn_enemy(game, fight=5, health=5, bounties=2)
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]

        _fight(game, colt)

        # 战斗3 + 2赏金 = 5 >= 5 成功；1基础 +1 = 2伤害
        assert enemy.damage == 2
        assert game.state.get_card_instance(colt).uses["ammo"] == 2

    def test_defeat_bounty_enemy_places_bounty_on_contracts(self):
        """击败带赏金的敌人：赏金合同+1赏金。"""
        game = self._setup(combat=4)
        colt = _equip(game, "tonys_38_long_colt_lv0", uses={"ammo": 3})
        contracts = _equip(game, "bounty_contracts_lv0", uses={"bounty": 0})
        _spawn_enemy(game, fight=3, health=2, bounties=1)
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]

        _fight(game, colt)

        assert game.state.get_card_instance("enemy_1") is None  # 被击败
        assert game.state.get_card_instance(contracts).uses["bounty"] == 1

    def test_no_ammo_plain_attack(self):
        """0弹药：不扣弹药、无加值，等同徒手攻击。"""
        game = self._setup(combat=3)
        colt = _equip(game, "tonys_38_long_colt_lv0", uses={"ammo": 0})
        enemy = _spawn_enemy(game, fight=3, health=5, bounties=2)
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]

        _fight(game, colt)

        assert enemy.damage == 1  # 无 +1 伤害
        assert game.state.get_card_instance(colt).uses["ammo"] == 0


class TestTrustyBullwhip:
    def _setup(self, **skills):
        game = _make_game([TrustyBullwhip], **skills)
        _register_asset_data(game, "trusty_bullwhip_lv0", slots=[SlotType.HAND])
        return game

    def test_agility_substitute_and_bonus_damage(self):
        """用敏捷代替战斗；成功横置长鞭：+1伤害。"""
        game = self._setup(combat=1, agility=4)
        whip = _equip(game, "trusty_bullwhip_lv0")
        enemy = _spawn_enemy(game, fight=4, health=5)
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]

        impl = game.card_registry.active_instances[whip]
        assert impl.activate(game.state, "inv1", on_success="damage") is True
        _fight(game, whip)

        # 敏捷4 >= 战斗4 成功；1基础 +1 = 2伤害
        assert enemy.damage == 2
        assert game.state.get_card_instance(whip).exhausted is True

    def test_auto_evade_on_success(self):
        """成功横置长鞭：自动躲避被攻击的敌人。"""
        game = self._setup(combat=1, agility=4)
        whip = _equip(game, "trusty_bullwhip_lv0")
        enemy = _spawn_enemy(game, fight=4, health=5)
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]
        inv = game.state.get_investigator("inv1")

        impl = game.card_registry.active_instances[whip]
        impl.activate(game.state, "inv1", on_success="evade")
        _fight(game, whip)

        assert enemy.damage == 1  # 基础伤害照旧（自动躲避为额外效果）
        assert enemy.exhausted is True
        assert "enemy_1" not in inv.threat_area
        assert "enemy_1" in game.state.locations["test_location"].enemies

    def test_no_substitute_when_not_armed(self):
        """未武装时长鞭不提供换技（徒手战斗1 vs 4 失败）。"""
        game = self._setup(combat=1, agility=4)
        whip = _equip(game, "trusty_bullwhip_lv0")
        enemy = _spawn_enemy(game, fight=4, health=5)
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]

        _fight(game, whip)

        assert enemy.damage == 0
        assert game.state.get_card_instance(whip).exhausted is False

    def test_exhausted_whip_no_success_effect(self):
        """长鞭已横置：成功后无额外效果（官方为可选发动）。"""
        game = self._setup(combat=1, agility=4)
        whip = _equip(game, "trusty_bullwhip_lv0")
        game.state.get_card_instance(whip).exhausted = True
        enemy = _spawn_enemy(game, fight=4, health=5)
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]

        impl = game.card_registry.active_instances[whip]
        impl.activate(game.state, "inv1", on_success="damage")
        _fight(game, whip)

        assert enemy.damage == 1  # 仅基础伤害


class TestTwilightBlade:
    def _setup(self, **skills):
        game = _make_game([TwilightBlade], **skills)
        _register_asset_data(game, "twilight_blade_lv0", slots=[SlotType.HAND])
        return game

    def test_willpower_substitute(self):
        """以意志代替战斗：意志4 vs 战斗4 成功。"""
        game = self._setup(combat=1, willpower=4)
        blade = _equip(game, "twilight_blade_lv0")
        enemy = _spawn_enemy(game, fight=4, health=5)
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]

        impl = game.card_registry.active_instances[blade]
        assert impl.activate(game.state, "inv1", use_willpower=True) is True
        _fight(game, blade)

        assert enemy.damage == 1

    def test_no_substitute_when_not_chosen(self):
        """选择不用意志：战斗1 vs 4 失败。"""
        game = self._setup(combat=1, willpower=4)
        blade = _equip(game, "twilight_blade_lv0")
        enemy = _spawn_enemy(game, fight=4, health=5)
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]

        impl = game.card_registry.active_instances[blade]
        impl.activate(game.state, "inv1", use_willpower=False)
        _fight(game, blade)

        assert enemy.damage == 0

    def test_playable_beneath_lists_events_and_skills(self):
        """戴安娜下方的事件/技能可经本能力打出（需匕首就绪）。"""
        game = self._setup()
        blade = _equip(game, "twilight_blade_lv0")
        for cid, ctype in (("evt", CardType.EVENT), ("skl", CardType.SKILL),
                           ("ast", CardType.ASSET)):
            game.register_card_data(CardData(
                id=cid, name=cid, name_cn=cid, type=ctype,
                card_class=PlayerClass.MYSTIC))
        game.state.scenario.vars["beneath_inv1"] = ["evt", "skl", "ast"]

        impl = game.card_registry.active_instances[blade]
        assert impl.playable_beneath(game.state, "inv1") == ["evt", "skl"]

        game.state.get_card_instance(blade).exhausted = True
        assert impl.playable_beneath(game.state, "inv1") == []


class TestTrenchCoat:
    def _setup(self, **skills):
        game = _make_game([TrenchCoat], **skills)
        _register_asset_data(game, "trench_coat_lv0", slots=[SlotType.BODY])
        return game

    def test_agility_bonus_during_evade(self):
        """躲避尝试 +1敏捷：敏捷3+1 vs 躲避4 成功。"""
        game = self._setup(agility=3)
        coat = _equip(game, "trench_coat_lv0")
        enemy = _spawn_enemy(game, evade=4)
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]
        inv = game.state.get_investigator("inv1")
        inv.actions_remaining = 3

        game.action_resolver.perform_action(
            "inv1", Action.EVADE, enemy_instance_id="enemy_1")

        assert enemy.exhausted is True  # 躲避成功
        assert "enemy_1" not in inv.threat_area

    def test_no_bonus_outside_evade(self):
        """非躲避的敏捷检定不加值（直接检定，无 EVADE 发起事件）。"""
        game = self._setup(agility=3)
        _equip(game, "trench_coat_lv0")
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]

        result = game.skill_test_engine.run_test(
            investigator_id="inv1", skill_type=Skill.AGILITY, difficulty=4)

        assert result.modified_skill == 3  # 无 +1
        assert result.success is False
