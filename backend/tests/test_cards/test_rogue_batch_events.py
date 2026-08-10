"""Behavior tests for the rogue event/skill batch:
Followed (0), Intel Report (0), "Let God sort them out..." (0),
Money Talks (0), Money Talks (2), Momentum (1), Hatchet Man (0).
"""

import pytest

from backend.cards.rogue.followed_lv0 import Followed
from backend.cards.rogue.hatchet_man_lv0 import HatchetMan
from backend.cards.rogue.intel_report_lv0 import IntelReport
from backend.cards.rogue.let_god_sort_them_out_lv0 import LetGodSortThemOut
from backend.cards.rogue.momentum_lv1 import Momentum
from backend.cards.rogue.money_talks_lv0 import MoneyTalks
from backend.cards.rogue.money_talks_lv2 import MoneyTalksLv2
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import (
    Action, ChaosTokenType, GameEvent, PlayerClass, Skill,
)
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_enemy_data, make_event_data, make_investigator_data,
    make_location_data, make_skill_data,
)


def _game(clues=3, **skills):
    g = Game("test")
    g.chaos_bag.seed(42)
    inv_data = make_investigator_data(**skills)
    g.register_card_data(inv_data)
    loc = make_location_data(clue_value=clues)
    g.register_card_data(loc)
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=clues)
    return g


def _emit(game, event, **kwargs):
    ctx = EventContext(game_state=game.state, event=event, **kwargs)
    game.event_bus.emit(ctx)
    return ctx


def _enemy(game, fight=3, health=5, evade=3, damage=1, horror=1,
           iid="enemy_1", engaged=True, preset_damage=0):
    data = make_enemy_data(fight=fight, health=health, evade=evade,
                           damage=damage, horror=horror)
    game.register_card_data(data)
    inst = CardInstance(
        instance_id=iid, card_id="test_enemy",
        owner_id="scenario", controller_id="scenario",
    )
    inst.damage = preset_damage
    game.state.cards_in_play[iid] = inst
    if engaged:
        game.state.get_investigator("inv1").threat_area.append(iid)
    else:
        game.state.get_location("test_location").enemies.append(iid)
    return inst


class TestFollowed:
    def test_full_flow_bonus_clue_and_no_aoo(self):
        """完整流程：+敌人伤害值的智力，成功额外发现1线索，不引发所选敌人AoO。"""
        g = _game(clues=3, intellect=3)
        g.card_registry.register_class(Followed)
        g.register_card_data(make_event_data(id="followed_lv0", cost=2))
        _enemy(g, preset_damage=2)  # 交战敌人，已受2点伤害
        inv = g.state.get_investigator("inv1")
        inv.hand = ["followed_lv0"]
        inv.resources = 3
        inv.actions_remaining = 3

        # 打出（PLAY 行动的 AoO 也被所选敌人豁免）
        ok = g.action_resolver.perform_action(
            "inv1", Action.PLAY, card_id="followed_lv0")
        assert ok is True
        assert inv.damage == 0 and inv.horror == 0  # AoO 被取消

        # 随后发起调查：3智力 + 2（敌人伤害）= 5 vs 隐蔽2，0标记成功
        g.chaos_bag.tokens = [ChaosTokenType.ZERO]
        ok = g.action_resolver.perform_action("inv1", Action.INVESTIGATE)
        assert ok is True
        loc = g.state.get_location("test_location")
        assert inv.clues == 2  # 基础1 + 尾随额外1
        assert loc.clues == 1
        assert inv.damage == 0 and inv.horror == 0  # 调查行动的 AoO 同样被取消

    def test_no_enemy_no_bonus(self):
        """地点无敌人：无加值，正常调查。"""
        g = _game(clues=2, intellect=3)
        g.card_registry.register_class(Followed)
        g.register_card_data(make_event_data(id="followed_lv0", cost=2))
        inv = g.state.get_investigator("inv1")
        inv.hand = ["followed_lv0"]
        g.action_resolver.perform_action("inv1", Action.PLAY, card_id="followed_lv0")
        g.chaos_bag.tokens = [ChaosTokenType.MINUS_2]
        g.action_resolver.perform_action("inv1", Action.INVESTIGATE)
        # 3 - 2 = 1 < 2 失败，无线索
        assert inv.clues == 0


class TestIntelReport:
    def test_base_discovers_one_clue(self):
        """打出：在你所在地点发现1个线索（引擎完整打出流程）。"""
        g = _game(clues=2)
        g.card_registry.register_class(IntelReport)
        g.register_card_data(make_event_data(id="intel_report_lv0", cost=2))
        inv = g.state.get_investigator("inv1")
        inv.hand = ["intel_report_lv0"]
        inv.resources = 5
        ok = g.action_resolver.perform_action(
            "inv1", Action.PLAY, card_id="intel_report_lv0")
        assert ok is True
        assert inv.clues == 1
        assert g.state.get_location("test_location").clues == 1
        assert inv.resources == 3

    def test_upgrades_via_extra_injection(self):
        """双升级（extra 注入）：+4资源，发现2个线索。"""
        g = _game(clues=3)
        g.card_registry.register_class(IntelReport)
        impl = g.card_registry.activate_card(
            "intel_report_lv0", "ir_tmp", g.event_bus, chaos_bag=g.chaos_bag)
        inv = g.state.get_investigator("inv1")
        inv.resources = 8
        ctx = _emit(g, GameEvent.CARD_PLAYED, investigator_id="inv1",
                    extra={"card_id": "intel_report_lv0",
                           "intel_report_two_clues": True})
        assert inv.clues == 2
        assert inv.resources == 6  # 追加费2
        assert ctx.extra["intel_report_upgraded_clues"] is True

    def test_remote_upgrade_discovers_two_away(self):
        """远程升级：在至多2步连接外的地点发现线索。"""
        g = _game(clues=0)
        loc2 = make_location_data(id="loc2", connections=["test_location"])
        g.register_card_data(loc2)
        g.add_location("loc2", loc2, clues=1)
        # test_location ↔ loc2 双向连接
        g.state.get_location("test_location").card_data.connections = ["loc2"]
        g.card_registry.register_class(IntelReport)
        g.card_registry.activate_card(
            "intel_report_lv0", "ir_tmp", g.event_bus, chaos_bag=g.chaos_bag)
        inv = g.state.get_investigator("inv1")
        inv.resources = 5
        ctx = _emit(g, GameEvent.CARD_PLAYED, investigator_id="inv1",
                    extra={"card_id": "intel_report_lv0",
                           "intel_report_remote_location": "loc2"})
        assert inv.clues == 1
        assert g.state.get_location("loc2").clues == 0
        assert inv.resources == 3
        assert ctx.extra["intel_report_upgraded_range"] is True


class TestLetGodSortThemOut:
    def _tracked_game(self):
        g = _game(clues=0)
        g.card_registry.register_class(LetGodSortThemOut)
        g.register_card_data(make_event_data(id="let_god_sort_them_out_lv0",
                                             cost=0))
        inv = g.state.get_investigator("inv1")
        inv.hand = ["let_god_sort_them_out_lv0"]
        impl = g.card_registry.activate_card(
            "let_god_sort_them_out_lv0", "lgsto_tmp", g.event_bus,
            chaos_bag=g.chaos_bag)
        return g, inv

    def test_play_after_6_health_defeated(self):
        """本回合击败生命合计≥6的敌人：入胜利陈列区、回合结束、+1经验。"""
        g, inv = self._tracked_game()
        g.register_card_data(make_enemy_data(health=4))
        _emit(g, GameEvent.INVESTIGATOR_TURN_BEGINS, investigator_id="inv1")
        for _ in range(2):  # 两只4生命敌人
            _emit(g, GameEvent.ENEMY_DEFEATED, investigator_id="inv1",
                  target="enemy_x", extra={"card_id": "test_enemy"})
        inv.actions_remaining = 2
        ctx = _emit(g, GameEvent.CARD_PLAYED, investigator_id="inv1",
                    extra={"card_id": "let_god_sort_them_out_lv0"})
        assert ctx.extra["let_god_sort_them_out"] is True
        assert inv.actions_remaining == 0
        assert g.state.scenario.vars["extra_experience"] == 1

        _emit(g, GameEvent.INVESTIGATOR_TURN_ENDS, investigator_id="inv1")
        assert "let_god_sort_them_out_lv0" in g.state.scenario.victory_display
        assert "let_god_sort_them_out_lv0" not in inv.hand

    def test_no_effect_below_threshold(self):
        """击败生命不足6：效果不发动。"""
        g, inv = self._tracked_game()
        g.register_card_data(make_enemy_data(health=3))
        _emit(g, GameEvent.INVESTIGATOR_TURN_BEGINS, investigator_id="inv1")
        _emit(g, GameEvent.ENEMY_DEFEATED, investigator_id="inv1",
              target="enemy_x", extra={"card_id": "test_enemy"})
        ctx = _emit(g, GameEvent.CARD_PLAYED, investigator_id="inv1",
                    extra={"card_id": "let_god_sort_them_out_lv0"})
        assert "let_god_sort_them_out" not in ctx.extra
        assert "let_god_sort_them_out_lv0" not in g.state.scenario.victory_display
        assert g.state.scenario.vars.get("extra_experience", 0) == 0


class TestMoneyTalks:
    def test_base_value_replaced_by_half_resources(self):
        """资源8→基础值4（原智力3）：自动打出，4 vs 难度4成功。"""
        g = _game(clues=0, intellect=3)
        g.card_registry.register_class(MoneyTalks)
        g.register_card_data(make_event_data(id="money_talks_lv0", cost=0,
                                             fast=True))
        inv = g.state.get_investigator("inv1")
        inv.hand = ["money_talks_lv0"]
        inv.resources = 8
        g.card_registry.activate_card(
            "money_talks_lv0", "mt_tmp", g.event_bus, chaos_bag=g.chaos_bag)

        g.chaos_bag.tokens = [ChaosTokenType.ZERO]
        result = g.skill_test_engine.run_test("inv1", Skill.INTELLECT, 4)
        assert result.modified_skill == 4
        assert result.success is True
        assert "money_talks_lv0" in inv.discard
        assert "money_talks_lv0" not in inv.hand

    def test_no_auto_play_when_worse(self):
        """资源一半不高于原技能值：不自动打出。"""
        g = _game(clues=0, intellect=3)
        g.card_registry.register_class(MoneyTalks)
        g.register_card_data(make_event_data(id="money_talks_lv0", cost=0,
                                             fast=True))
        inv = g.state.get_investigator("inv1")
        inv.hand = ["money_talks_lv0"]
        inv.resources = 4  # 一半=2 ≤ 3
        g.card_registry.activate_card(
            "money_talks_lv0", "mt_tmp", g.event_bus, chaos_bag=g.chaos_bag)
        g.chaos_bag.tokens = [ChaosTokenType.ZERO]
        result = g.skill_test_engine.run_test("inv1", Skill.INTELLECT, 3)
        assert result.modified_skill == 3
        assert "money_talks_lv0" in inv.hand


class TestMoneyTalksLv2:
    def test_other_investigator_base_and_draw(self):
        """可为任意调查员的检定发动：执行者基础值=持有者资源一半，持有者抽1。"""
        g = _game(clues=0, intellect=3)
        other_data = make_investigator_data(id="inv2")
        g.register_card_data(other_data)
        g.add_investigator("inv2", other_data, starting_location="test_location")
        g.card_registry.register_class(MoneyTalksLv2)
        g.register_card_data(make_event_data(id="money_talks_lv2", cost=0,
                                             fast=True))
        holder = g.state.get_investigator("inv2")
        holder.hand = ["money_talks_lv2"]
        holder.deck = ["top_card"]
        holder.resources = 10  # 一半=5
        g.card_registry.activate_card(
            "money_talks_lv2", "mt2_tmp", g.event_bus, chaos_bag=g.chaos_bag)

        g.chaos_bag.tokens = [ChaosTokenType.ZERO]
        result = g.skill_test_engine.run_test("inv1", Skill.INTELLECT, 5)
        assert result.modified_skill == 5
        assert result.success is True
        assert "money_talks_lv2" in holder.discard
        assert "top_card" in holder.hand  # 抽1张牌


class TestMomentum:
    def test_success_reduces_next_test_difficulty(self):
        """成功超2（含1百搭图标）：下一次检定难度-2（难度4→2，智力3成功）。"""
        g = _game(clues=0, intellect=3)
        g.card_registry.register_class(Momentum)
        g.register_card_data(make_skill_data(id="momentum_lv1",
                                             skill_icons={"wild": 1}))
        # 持久监听实例（模拟抽到后经 persistent_in_hand 注册）
        g.card_registry.activate_card(
            "momentum_lv1", "mom_persist", g.event_bus, chaos_bag=g.chaos_bag)

        g.chaos_bag.tokens = [ChaosTokenType.ZERO]
        first = g.skill_test_engine.run_test(
            "inv1", Skill.INTELLECT, 2, committed_card_ids=["momentum_lv1"])
        assert first.success is True  # 3+1 vs 2，超2

        second = g.skill_test_engine.run_test("inv1", Skill.INTELLECT, 4)
        assert second.difficulty == 2  # 难度-2
        assert second.success is True

    def test_no_carryover_without_success(self):
        g = _game(clues=0, intellect=3)
        g.card_registry.register_class(Momentum)
        g.register_card_data(make_skill_data(id="momentum_lv1",
                                             skill_icons={"wild": 1}))
        g.card_registry.activate_card(
            "momentum_lv1", "mom_persist", g.event_bus, chaos_bag=g.chaos_bag)
        g.chaos_bag.tokens = [ChaosTokenType.MINUS_2]
        first = g.skill_test_engine.run_test(
            "inv1", Skill.INTELLECT, 3, committed_card_ids=["momentum_lv1"])
        assert first.success is False  # 3+1-2=2 < 3
        second = g.skill_test_engine.run_test("inv1", Skill.INTELLECT, 4)
        assert second.difficulty == 4  # 无减难度
        assert second.success is False


class TestHatchetMan:
    def test_evade_then_bonus_damage(self):
        """躲避成功后：该敌人本回合下一次受伤+1。"""
        g = _game(clues=0, agility=3)
        g.card_registry.register_class(HatchetMan)
        g.register_card_data(make_skill_data(id="hatchet_man_lv0",
                                             skill_icons={}))
        # 持久监听实例（模拟抽到后经 persistent_in_hand 注册）
        g.card_registry.activate_card(
            "hatchet_man_lv0", "hm_persist", g.event_bus, chaos_bag=g.chaos_bag)
        _enemy(g, health=5, evade=3)
        inv = g.state.get_investigator("inv1")
        inv.actions_remaining = 3
        g.chaos_bag.tokens = [ChaosTokenType.ZERO]
        ok = g.action_resolver.perform_action(
            "inv1", Action.EVADE, enemy_instance_id="enemy_1",
            committed_cards=["hatchet_man_lv0"])
        assert ok is True
        enemy = g.state.get_card_instance("enemy_1")
        assert enemy.exhausted is True  # 已躲避

        g.damage_engine.deal_damage_to_enemy("enemy_1", 1, source="punch",
                                             investigator_id="inv1")
        assert enemy.damage == 2  # 1 + 刽子手1

    def test_no_bonus_without_commit(self):
        g = _game(clues=0, agility=3)
        g.card_registry.register_class(HatchetMan)
        _enemy(g, health=5, evade=3)
        inv = g.state.get_investigator("inv1")
        inv.actions_remaining = 3
        g.chaos_bag.tokens = [ChaosTokenType.ZERO]
        g.action_resolver.perform_action(
            "inv1", Action.EVADE, enemy_instance_id="enemy_1")
        g.damage_engine.deal_damage_to_enemy("enemy_1", 1, source="punch",
                                             investigator_id="inv1")
        assert g.state.get_card_instance("enemy_1").damage == 1
