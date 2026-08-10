"""Behavior tests for the rogue talent/ally batch:
Hard Knocks (4), Moxie (3), High Roller (2), Gregory Gry (0),
Investments (0), Haste (2), Lucky Cigarette Case (0).
"""

import pytest

from backend.cards.rogue.gregory_gry_lv0 import GregoryGry
from backend.cards.rogue.hard_knocks_lv4 import HardKnocksLv4
from backend.cards.rogue.haste_lv2 import Haste
from backend.cards.rogue.high_roller_lv2 import HighRoller
from backend.cards.rogue.investments_lv0 import Investments
from backend.cards.rogue.lucky_cigarette_case_lv0 import LuckyCigaretteCase
from backend.cards.rogue.moxie_lv3 import MoxieLv3
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import (
    Action, ChaosTokenType, GameEvent, PlayerClass, Skill,
)
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_asset_data, make_investigator_data, make_location_data,
)


def _game(**skills):
    g = Game("test")
    g.chaos_bag.seed(42)
    inv_data = make_investigator_data(**skills)
    g.register_card_data(inv_data)
    loc = make_location_data(clue_value=0)
    g.register_card_data(loc)
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)
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


class TestHardKnocksLv4:
    def test_spend_from_card_first(self):
        """默认优先扣本卡资源标记：本次检定+1战斗。"""
        g = _game(combat=3)
        impl, iid = _equip(g, "hard_knocks_lv4", HardKnocksLv4,
                           uses={"resourcess": 2})
        inv = g.state.get_investigator("inv1")
        inv.resources = 1
        assert impl.spend(g.state, "inv1", Skill.COMBAT) is True
        inst = g.state.get_card_instance(iid)
        assert inst.uses["resourcess"] == 1
        assert inv.resources == 1  # 资源池未动

        g.chaos_bag.tokens = [ChaosTokenType.ZERO]
        result = g.skill_test_engine.run_test("inv1", Skill.COMBAT, 4)
        assert result.modified_skill == 4
        assert result.success is True

    def test_fallback_to_pool_and_replenish(self):
        """本卡耗尽后回落资源池；每轮开始补满至2。"""
        g = _game(agility=3)
        impl, iid = _equip(g, "hard_knocks_lv4", HardKnocksLv4,
                           uses={"resourcess": 2})
        inv = g.state.get_investigator("inv1")
        inv.resources = 1
        assert impl.spend(g.state, "inv1", Skill.AGILITY) is True
        assert impl.spend(g.state, "inv1", Skill.AGILITY) is True
        assert g.state.get_card_instance(iid).uses["resourcess"] == 0
        assert impl.spend(g.state, "inv1", Skill.AGILITY) is True  # 回落资源池
        assert inv.resources == 0
        assert impl.spend(g.state, "inv1", Skill.AGILITY) is False  # 两边都空
        assert impl.spend(g.state, "inv1", Skill.WILLPOWER) is False  # 仅战斗/敏捷

        _emit(g, GameEvent.ROUND_BEGINS)
        assert g.state.get_card_instance(iid).uses["resourcess"] == 2


class TestMoxieLv3:
    def test_passive_boost_and_pump(self):
        """被动+1意志/+1敏捷；花费泵可叠加。"""
        g = _game(willpower=3)
        impl, iid = _equip(g, "moxie_lv3", MoxieLv3, health=3, sanity=1)
        inv = g.state.get_investigator("inv1")
        inv.resources = 2
        assert impl.spend(g.state, "inv1", Skill.WILLPOWER) is True
        g.chaos_bag.tokens = [ChaosTokenType.ZERO]
        result = g.skill_test_engine.run_test("inv1", Skill.WILLPOWER, 5)
        assert result.modified_skill == 5  # 3 + 1被动 + 1泵
        assert result.success is True

    def test_soak_damage_and_horror(self):
        """非直接伤害/恐惧先分配给本卡（生命3/神智1）。"""
        g = _game()
        impl, iid = _equip(g, "moxie_lv3", MoxieLv3, health=3, sanity=1)
        inst = g.state.get_card_instance(iid)
        ctx = _emit(g, GameEvent.DAMAGE_ASSIGNED, investigator_id="inv1",
                    amount=2, source="enemy_1")
        assert inst.damage == 2
        assert ctx.amount == 0

        ctx = _emit(g, GameEvent.HORROR_ASSIGNED, investigator_id="inv1",
                    amount=1, source="enemy_1")
        assert inst.horror == 1
        assert ctx.amount == 0
        # 承满神智：被击败离场
        inv = g.state.get_investigator("inv1")
        assert iid not in inv.play_area
        assert "moxie_lv3" in inv.discard
        assert ctx.extra["moxie_lv3_defeated"] is True


class TestHighRoller:
    def test_boost_and_refund_on_success(self):
        """花3消耗：+2技能值；成功返还3。"""
        g = _game(combat=3)
        impl, iid = _equip(g, "high_roller_lv2", HighRoller)
        inv = g.state.get_investigator("inv1")
        inv.resources = 5
        assert impl.activate(g.state, "inv1") is True
        assert inv.resources == 2
        assert g.state.get_card_instance(iid).exhausted is True

        g.chaos_bag.tokens = [ChaosTokenType.ZERO]
        result = g.skill_test_engine.run_test("inv1", Skill.COMBAT, 5)
        assert result.modified_skill == 5
        assert result.success is True
        assert inv.resources == 5  # 返还3
        assert result.extra.get("high_roller_refund") == 3

    def test_no_refund_on_failure(self):
        g = _game(combat=3)
        impl, iid = _equip(g, "high_roller_lv2", HighRoller)
        inv = g.state.get_investigator("inv1")
        inv.resources = 5
        impl.activate(g.state, "inv1")
        g.chaos_bag.tokens = [ChaosTokenType.MINUS_3]
        result = g.skill_test_engine.run_test("inv1", Skill.COMBAT, 5)
        assert result.success is False
        assert inv.resources == 2


class TestGregoryGry:
    def test_wager_payout_on_margin(self):
        """从卡上押2资源：成功超难度≥2则获得2资源。"""
        g = _game()
        impl, iid = _equip(g, "gregory_gry_lv0", GregoryGry,
                           uses={"resourcess": 9}, health=1, sanity=2)
        inv = g.state.get_investigator("inv1")
        inv.resources = 4
        assert impl.spend(g.state, "inv1", 2) is True
        assert g.state.get_card_instance(iid).uses["resourcess"] == 7

        ctx = _emit(g, GameEvent.SKILL_TEST_SUCCESSFUL, investigator_id="inv1",
                    skill_type=Skill.COMBAT, success=True,
                    modified_skill=5, difficulty=3)
        assert inv.resources == 6
        assert ctx.extra["gregory_gry_payout"] == 2

    def test_no_payout_below_margin(self):
        g = _game()
        impl, iid = _equip(g, "gregory_gry_lv0", GregoryGry,
                           uses={"resourcess": 9}, health=1, sanity=2)
        inv = g.state.get_investigator("inv1")
        inv.resources = 4
        impl.spend(g.state, "inv1", 3)
        _emit(g, GameEvent.SKILL_TEST_SUCCESSFUL, investigator_id="inv1",
              skill_type=Skill.COMBAT, success=True,
              modified_skill=4, difficulty=3)  # margin 1 < 3
        assert inv.resources == 4
        assert impl.spend(g.state, "inv1", 7) is False  # 超过3的上限


class TestInvestments:
    def test_store_and_cash_out(self):
        """存放2补给后兑现：+2资源并弃置本卡。"""
        g = _game()
        impl, iid = _equip(g, "investments_lv0", Investments,
                           uses={"suppliess": 0})
        inv = g.state.get_investigator("inv1")
        inv.resources = 1
        inst = g.state.get_card_instance(iid)
        assert impl.store(g.state, "inv1") is True
        assert inst.uses["suppliess"] == 1
        assert inst.exhausted is True
        inst.exhausted = False  # 下回合准备
        assert impl.store(g.state, "inv1") is True
        assert inst.uses["suppliess"] == 2

        assert impl.cash_out(g.state, "inv1") is True
        assert inv.resources == 3
        assert iid not in inv.play_area
        assert "investments_lv0" in inv.discard
        assert iid not in g.state.cards_in_play


class TestHaste:
    def test_same_action_twice_grants_extra(self):
        """连续两个相同行动：消耗本卡，+1行动。"""
        g = _game()
        impl, iid = _equip(g, "haste_lv2", Haste)
        inv = g.state.get_investigator("inv1")
        inv.actions_remaining = 2
        _emit(g, GameEvent.ACTION_PERFORMED, investigator_id="inv1",
              action=Action.MOVE)
        assert inv.actions_remaining == 2
        ctx = _emit(g, GameEvent.ACTION_PERFORMED, investigator_id="inv1",
                    action=Action.MOVE)
        assert inv.actions_remaining == 3
        assert g.state.get_card_instance(iid).exhausted is True
        assert ctx.extra["haste_extra_action"] == "MOVE"

    def test_streak_broken_by_different_action(self):
        g = _game()
        impl, iid = _equip(g, "haste_lv2", Haste)
        inv = g.state.get_investigator("inv1")
        inv.actions_remaining = 2
        _emit(g, GameEvent.ACTION_PERFORMED, investigator_id="inv1",
              action=Action.MOVE)
        _emit(g, GameEvent.ACTION_PERFORMED, investigator_id="inv1",
              action=Action.INVESTIGATE)
        assert inv.actions_remaining == 2
        assert g.state.get_card_instance(iid).exhausted is False


class TestLuckyCigaretteCase:
    def test_draw_on_success_by_2(self):
        """成功超2：消耗本卡，抽1张牌。"""
        g = _game()
        impl, iid = _equip(g, "lucky_cigarette_case_lv0", LuckyCigaretteCase)
        inv = g.state.get_investigator("inv1")
        inv.deck = ["top_card"]
        ctx = _emit(g, GameEvent.SKILL_TEST_SUCCESSFUL, investigator_id="inv1",
                    skill_type=Skill.COMBAT, success=True,
                    modified_skill=5, difficulty=3)
        assert inv.hand == ["top_card"]
        assert g.state.get_card_instance(iid).exhausted is True
        assert ctx.extra["lucky_cigarette_case_draw"] is True

    def test_no_draw_on_margin_1(self):
        g = _game()
        impl, iid = _equip(g, "lucky_cigarette_case_lv0", LuckyCigaretteCase)
        inv = g.state.get_investigator("inv1")
        inv.deck = ["top_card"]
        _emit(g, GameEvent.SKILL_TEST_SUCCESSFUL, investigator_id="inv1",
              skill_type=Skill.COMBAT, success=True,
              modified_skill=4, difficulty=3)
        assert inv.hand == []
        assert g.state.get_card_instance(iid).exhausted is False
