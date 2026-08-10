"""Behavior tests for the rogue asset batch:
Fence (1), Garrote Wire (2), Henry Wan (0), Joey "The Rat" Vigil (3),
Lola Santiago (3), Obfuscation (0).
"""

import pytest

from backend.cards.rogue.fence_lv1 import Fence
from backend.cards.rogue.garrote_wire_lv2 import GarroteWire
from backend.cards.rogue.henry_wan_lv0 import HenryWan
from backend.cards.rogue.joey_the_rat_vigil_lv3 import JoeyTheRatVigil
from backend.cards.rogue.lola_santiago_lv3 import LolaSantiago
from backend.cards.rogue.obfuscation_lv0 import Obfuscation
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import (
    Action, ChaosTokenType, GameEvent, PlayerClass, Skill, SlotType,
)
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_asset_data, make_enemy_data, make_event_data,
    make_investigator_data, make_location_data,
)


def _game(clues=0, shroud=2, **skills):
    g = Game("test")
    g.chaos_bag.seed(42)
    inv_data = make_investigator_data(**skills)
    g.register_card_data(inv_data)
    loc = make_location_data(clue_value=clues, shroud=shroud)
    g.register_card_data(loc)
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=clues)
    return g


def _equip(game, card_id, impl_cls, uses=None, owner="inv1", **data_kwargs):
    if game.state.get_card_data(card_id) is None:
        game.register_card_data(make_asset_data(
            id=card_id, card_class=PlayerClass.ROGUE, uses=uses, **data_kwargs))
    game.card_registry.register_class(impl_cls)
    iid = game.state.next_instance_id()
    inst = CardInstance(
        instance_id=iid, card_id=card_id, owner_id=owner, controller_id=owner,
        uses=dict(uses or {}),
    )
    game.state.cards_in_play[iid] = inst
    game.state.get_investigator(owner).play_area.append(iid)
    impl = game.card_registry.activate_card(
        card_id, iid, game.event_bus, chaos_bag=game.chaos_bag)
    return impl, iid


def _emit(game, event, **kwargs):
    ctx = EventContext(game_state=game.state, event=event, **kwargs)
    game.event_bus.emit(ctx)
    return ctx


def _enemy(game, fight=3, health=3, evade=3, damage=1, horror=1,
           iid="enemy_1", preset_damage=0):
    data = make_enemy_data(fight=fight, health=health, evade=evade,
                           damage=damage, horror=horror)
    game.register_card_data(data)
    inst = CardInstance(
        instance_id=iid, card_id="test_enemy",
        owner_id="scenario", controller_id="scenario",
    )
    inst.damage = preset_damage
    game.state.cards_in_play[iid] = inst
    game.state.get_investigator("inv1").threat_area.append(iid)
    return inst


class TestFence:
    def test_illicit_event_gains_fast(self):
        """你的回合打出非法事件：消耗本卡，退还1行动（视为快速）。"""
        g = _game()
        impl, iid = _equip(g, "fence_lv1", Fence, traits=["connection", "illicit"])
        illicit = make_event_data(id="illicit_event", cost=1)
        illicit.traits = ["illicit"]
        g.register_card_data(illicit)
        inv = g.state.get_investigator("inv1")
        inv.hand = ["illicit_event"]
        inv.resources = 3
        inv.actions_remaining = 3
        _emit(g, GameEvent.INVESTIGATOR_TURN_BEGINS, investigator_id="inv1")

        ok = g.action_resolver.perform_action(
            "inv1", Action.PLAY, card_id="illicit_event")
        assert ok is True
        assert inv.actions_remaining == 3  # 行动被退还
        assert g.state.get_card_instance(iid).exhausted is True

    def test_fast_illicit_refunds_resource(self):
        """已有快速的非法卡：改为费用-1（事后退还1资源）。"""
        g = _game()
        impl, iid = _equip(g, "fence_lv1", Fence, traits=["connection", "illicit"])
        fast_illicit = make_event_data(id="fast_illicit", cost=2, fast=True)
        fast_illicit.traits = ["illicit"]
        g.register_card_data(fast_illicit)
        inv = g.state.get_investigator("inv1")
        inv.hand = ["fast_illicit"]
        inv.resources = 5
        inv.actions_remaining = 3
        _emit(g, GameEvent.INVESTIGATOR_TURN_BEGINS, investigator_id="inv1")

        g.action_resolver.perform_action("inv1", Action.PLAY, card_id="fast_illicit")
        assert inv.resources == 4  # 付2退1
        assert inv.actions_remaining == 3  # 快速本就不耗行动

    def test_non_illicit_no_trigger(self):
        g = _game()
        impl, iid = _equip(g, "fence_lv1", Fence, traits=["connection", "illicit"])
        normal = make_event_data(id="normal_event", cost=1)
        g.register_card_data(normal)
        inv = g.state.get_investigator("inv1")
        inv.hand = ["normal_event"]
        inv.resources = 3
        inv.actions_remaining = 3
        _emit(g, GameEvent.INVESTIGATOR_TURN_BEGINS, investigator_id="inv1")
        g.action_resolver.perform_action("inv1", Action.PLAY, card_id="normal_event")
        assert inv.actions_remaining == 2
        assert g.state.get_card_instance(iid).exhausted is False


class TestGarroteWire:
    def test_fight_one_health_enemy(self):
        """对剩余生命恰好1的敌人：+2战斗攻击（3+2 vs 3，成功击杀）。"""
        g = _game(combat=3)
        impl, iid = _equip(g, "garrote_wire_lv2", GarroteWire,
                           traits=["item", "weapon"])
        _enemy(g, health=3, preset_damage=2)  # 剩余生命1
        inv = g.state.get_investigator("inv1")
        inv.actions_remaining = 3
        _emit(g, GameEvent.INVESTIGATOR_TURN_BEGINS, investigator_id="inv1")

        assert impl.activate(g.state, "inv1", enemy_instance_id="enemy_1") is True
        assert g.state.get_card_instance(iid).exhausted is True
        g.chaos_bag.tokens = [ChaosTokenType.ZERO]
        ok = g.action_resolver.perform_action(
            "inv1", Action.FIGHT, enemy_instance_id="enemy_1",
            weapon_instance_id=iid)
        assert ok is True
        assert "enemy_1" not in g.state.cards_in_play  # 被击败

    def test_rejects_healthy_enemy(self):
        """剩余生命不为1的敌人无法使用。"""
        g = _game(combat=3)
        impl, iid = _equip(g, "garrote_wire_lv2", GarroteWire,
                           traits=["item", "weapon"])
        _enemy(g, health=3, preset_damage=0)
        _emit(g, GameEvent.INVESTIGATOR_TURN_BEGINS, investigator_id="inv1")
        assert impl.activate(g.state, "inv1", enemy_instance_id="enemy_1") is False
        assert g.state.get_card_instance(iid).exhausted is False


class TestHenryWan:
    def test_safe_reveals_gain_resources(self):
        """揭示2枚安全标记后停止：每枚获得1资源。"""
        g = _game()
        impl, iid = _equip(g, "henry_wan_lv0", HenryWan, health=1, sanity=2)
        inv = g.state.get_investigator("inv1")
        inv.resources = 1
        g.chaos_bag.tokens = [ChaosTokenType.PLUS_1, ChaosTokenType.ZERO]
        assert impl.activate(g.state, "inv1", stop_after=2,
                             reward="resource") is True
        assert inv.resources == 3
        assert g.state.get_card_instance(iid).exhausted is True

    def test_safe_reveals_draw_cards(self):
        """默认奖励为抽牌：每枚抽1张。"""
        g = _game()
        impl, iid = _equip(g, "henry_wan_lv0", HenryWan, health=1, sanity=2)
        inv = g.state.get_investigator("inv1")
        inv.deck = ["c1", "c2"]
        g.chaos_bag.tokens = [ChaosTokenType.ZERO]
        assert impl.activate(g.state, "inv1", stop_after=2) is True
        assert inv.hand == ["c1", "c2"]

    def test_bad_symbol_means_nothing(self):
        """揭示到[skull]：无事发生。"""
        g = _game()
        impl, iid = _equip(g, "henry_wan_lv0", HenryWan, health=1, sanity=2)
        inv = g.state.get_investigator("inv1")
        inv.resources = 1
        inv.deck = ["c1"]
        g.chaos_bag.tokens = [ChaosTokenType.SKULL]
        assert impl.activate(g.state, "inv1") is True
        assert inv.resources == 1
        assert inv.hand == []


class TestJoeyTheRatVigil:
    def test_play_item_from_hand(self):
        """快速：花1资源+物品费用，从手牌打出物品支援。"""
        g = _game()
        impl, iid = _equip(g, "joey_the_rat_vigil_lv3", JoeyTheRatVigil,
                           health=3, sanity=2)
        g.register_card_data(make_asset_data(
            id="test_item", cost=2, card_class=PlayerClass.ROGUE,
            slots=[SlotType.HAND], traits=["item", "weapon"]))
        inv = g.state.get_investigator("inv1")
        inv.hand = ["test_item"]
        inv.resources = 5
        assert impl.play_item(g.state, "inv1", "test_item") is True
        assert inv.resources == 2  # 1 + 2
        assert "test_item" not in inv.hand
        assert len(inv.play_area) == 2
        item_iid = next(i for i in inv.play_area if i != iid)
        assert g.slot_managers["inv1"].get_cards_in_slot(SlotType.HAND) == [item_iid]

    def test_play_item_rejects_non_item(self):
        g = _game()
        impl, iid = _equip(g, "joey_the_rat_vigil_lv3", JoeyTheRatVigil,
                           health=3, sanity=2)
        g.register_card_data(make_asset_data(
            id="test_tome", cost=1, card_class=PlayerClass.ROGUE,
            traits=["tome"]))
        inv = g.state.get_investigator("inv1")
        inv.hand = ["test_tome"]
        inv.resources = 5
        assert impl.play_item(g.state, "inv1", "test_tome") is False
        assert inv.resources == 5

    def test_pawn_item_gains_2(self):
        """快速：弃置在场物品支援，获得2资源。"""
        g = _game()
        impl, iid = _equip(g, "joey_the_rat_vigil_lv3", JoeyTheRatVigil,
                           health=3, sanity=2)
        g.register_card_data(make_asset_data(
            id="test_item", cost=1, card_class=PlayerClass.ROGUE,
            traits=["item"]))
        inv = g.state.get_investigator("inv1")
        item_iid = g.state.next_instance_id()
        g.state.cards_in_play[item_iid] = CardInstance(
            instance_id=item_iid, card_id="test_item",
            owner_id="inv1", controller_id="inv1")
        inv.play_area.append(item_iid)
        inv.resources = 0
        assert impl.pawn_item(g.state, "inv1", item_iid) is True
        assert inv.resources == 2
        assert item_iid not in inv.play_area
        assert "test_item" in inv.discard


class TestLolaSantiago:
    def test_passive_boost(self):
        """+1智力/+1敏捷。"""
        g = _game(intellect=3)
        impl, iid = _equip(g, "lola_santiago_lv3", LolaSantiago,
                           health=2, sanity=2)
        g.chaos_bag.tokens = [ChaosTokenType.ZERO]
        result = g.skill_test_engine.run_test("inv1", Skill.INTELLECT, 4)
        assert result.modified_skill == 4
        assert result.success is True

    def test_discover_clue_for_shroud_cost(self):
        """快速：消耗+花X资源（X=隐蔽值2），发现1线索。"""
        g = _game(clues=1, shroud=2)
        impl, iid = _equip(g, "lola_santiago_lv3", LolaSantiago,
                           health=2, sanity=2)
        inv = g.state.get_investigator("inv1")
        inv.resources = 3
        assert impl.activate(g.state, "inv1") is True
        assert inv.resources == 1
        assert inv.clues == 1
        assert g.state.get_location("test_location").clues == 0
        assert g.state.get_card_instance(iid).exhausted is True

    def test_cannot_afford_shroud(self):
        g = _game(clues=1, shroud=4)
        impl, iid = _equip(g, "lola_santiago_lv3", LolaSantiago,
                           health=2, sanity=2)
        inv = g.state.get_investigator("inv1")
        inv.resources = 2
        assert impl.activate(g.state, "inv1") is False


class TestObfuscation:
    def test_cancel_aoo_spends_charge(self):
        """趁乱攻击：自动花1充能取消（"chargess" 笔误键兼容）。"""
        g = _game()
        impl, iid = _equip(g, "obfuscation_lv0", Obfuscation,
                           uses={"chargess": 3})
        _enemy(g)  # 交战且就绪
        inv = g.state.get_investigator("inv1")
        inv.actions_remaining = 3
        ok = g.action_resolver.perform_action("inv1", Action.RESOURCE)
        assert ok is True
        assert inv.damage == 0 and inv.horror == 0  # AoO 被取消
        assert g.state.get_card_instance(iid).uses["chargess"] == 2

    def test_no_charges_no_cancel(self):
        g = _game()
        impl, iid = _equip(g, "obfuscation_lv0", Obfuscation,
                           uses={"chargess": 0})
        _enemy(g)
        inv = g.state.get_investigator("inv1")
        inv.actions_remaining = 3
        g.action_resolver.perform_action("inv1", Action.RESOURCE)
        assert inv.damage == 1 and inv.horror == 1  # AoO 正常命中
