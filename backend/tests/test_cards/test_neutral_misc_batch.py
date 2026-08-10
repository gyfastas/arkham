"""Tests for neutral misc asset/event/skill batch:
Thermos / Until the End of Time / Versatile / The Tower • XVI /
Unsolved Case / Whispers from the Deep.
"""

import importlib

import pytest

from backend.cards.neutral.thermos_lv0 import Thermos
from backend.cards.neutral.unsolved_case_lv0 import UnsolvedCase
from backend.cards.neutral.until_the_end_of_time_lv0 import UntilTheEndOfTime
from backend.cards.neutral.versatile_lv2 import Versatile
from backend.cards.neutral.whispers_from_the_deep_lv0 import WhispersFromTheDeep

# 模块名含 U+2022，不能用于 import 语句，改经 importlib 导入
TheTowerXVI = importlib.import_module(
    "backend.cards.neutral.the_tower_•_xvi_lv0").TheTowerXVI
from backend.engine.event_bus import EventContext
from backend.models.enums import (
    CardType, ChaosTokenType, GameEvent, PlayerClass, Skill,
)
from backend.models.state import CardData, CardInstance
from backend.tests.conftest import make_location_data


def _emit(game, event, inv_id="test_investigator", **kwargs):
    ctx = EventContext(
        game_state=game.state, event=event, investigator_id=inv_id, **kwargs
    )
    game.event_bus.emit(ctx)
    return ctx


def _register(game, impl_cls, instance_id="impl_1"):
    impl = impl_cls(instance_id)
    impl.register(game.event_bus, instance_id)
    return impl


def _equip(game, card_id, instance_id, uses=None, inv_id="test_investigator"):
    inv = game.state.get_investigator(inv_id)
    ci = CardInstance(
        instance_id=instance_id, card_id=card_id,
        owner_id=inv_id, controller_id=inv_id,
    )
    if uses:
        ci.uses = dict(uses)
    game.state.cards_in_play[instance_id] = ci
    inv.play_area.append(instance_id)
    return ci


class TestThermos:
    def _setup(self, game):
        game.register_card_data(CardData(
            id="thermos_lv0", name="Thermos", name_cn="暖水瓶",
            type=CardType.ASSET, card_class=PlayerClass.NEUTRAL,
            uses={"suppliess": 3},  # 数据笔误键，入场时应规范化
        ))
        impl = _register(game, Thermos, "thermos_1")
        inst = _equip(game, "thermos_lv0", "thermos_1",
                      uses={"suppliess": 3})
        _emit(game, GameEvent.CARD_ENTERS_PLAY, target="thermos_1",
              extra={"card_id": "thermos_lv0"})
        return impl, inst

    def test_uses_key_normalized_on_enter_play(self, game):
        """数据笔误 "suppliess" 入场时规范化为 "supplies"。"""
        _, inst = self._setup(game)
        assert inst.uses == {"supplies": 3}

    def test_heal_damage(self, game):
        """花1补给横置：治愈1伤害。"""
        impl, inst = self._setup(game)
        inv = game.state.get_investigator("test_investigator")
        inv.damage = 2

        assert impl.activate_heal_damage(game.state, "test_investigator") is True
        assert inv.damage == 1
        assert inst.uses["supplies"] == 2
        assert inst.exhausted is True

    def test_heal_two_with_trauma(self, game):
        """目标有2+肉体/精神创伤时治愈2点。"""
        impl, inst = self._setup(game)
        inv = game.state.get_investigator("test_investigator")
        inv.damage = 2
        inv.physical_trauma = 2

        assert impl.activate_heal_damage(game.state, "test_investigator") is True
        assert inv.damage == 0

        # 精神创伤侧
        inst.exhausted = False
        inv.horror = 2
        inv.mental_trauma = 2
        assert impl.activate_heal_horror(game.state, "test_investigator") is True
        assert inv.horror == 0
        assert inst.uses["supplies"] == 1  # 3 - 2 次使用

    def test_exhausted_or_empty_cannot_activate(self, game):
        impl, inst = self._setup(game)
        inv = game.state.get_investigator("test_investigator")
        inv.damage = 1
        inst.exhausted = True
        assert impl.activate_heal_damage(game.state, "test_investigator") is False
        inst.exhausted = False
        inst.uses["supplies"] = 0
        assert impl.activate_heal_damage(game.state, "test_investigator") is False

    def test_heal_other_investigator_at_location(self, game):
        """可治愈同地点的其他调查员；不同地点不行。"""
        impl, inst = self._setup(game)
        from backend.tests.conftest import make_investigator_data
        inv2_data = make_investigator_data(id="inv2")
        game.register_card_data(inv2_data)
        game.add_investigator("inv2", inv2_data,
                              starting_location="test_location")
        inv2 = game.state.get_investigator("inv2")
        inv2.damage = 1

        assert impl.activate_heal_damage(
            game.state, "test_investigator",
            target_investigator_id="inv2") is True
        assert inv2.damage == 0

        inst.exhausted = False
        inv2.location_id = "elsewhere"
        inv2.damage = 1
        assert impl.activate_heal_damage(
            game.state, "test_investigator",
            target_investigator_id="inv2") is False


class TestUntilTheEndOfTime:
    def _setup(self, game):
        game.register_card_data(CardData(
            id="until_the_end_of_time_lv0", name="Until the End of Time",
            name_cn="时间尽头", type=CardType.ASSET,
            card_class=PlayerClass.NEUTRAL, health=2, sanity=2,
        ))
        impl = _register(game, UntilTheEndOfTime, "utet_1")
        inst = _equip(game, "until_the_end_of_time_lv0", "utet_1")
        return impl, inst

    def test_direct_damage_assignment_and_defeat(self, game):
        """直接伤害可分配到本卡；承伤池耗尽后被击败离场。"""
        impl, inst = self._setup(game)
        inv = game.state.get_investigator("test_investigator")

        assert impl.can_assign_direct(game.state, "test_investigator") is True
        assert impl.assign_direct(game.state, "test_investigator",
                                  damage=1) is True
        assert inst.damage == 1
        assert "utet_1" in inv.play_area

        # 第二次分配达到生命上限：被击败
        assert impl.assign_direct(game.state, "test_investigator",
                                  damage=1) is True
        assert game.state.get_card_instance("utet_1") is None
        assert "utet_1" not in inv.play_area
        assert "until_the_end_of_time_lv0" in inv.discard

    def test_direct_horror_assignment(self, game):
        """直接恐惧同样可分配（2理智上限）。"""
        impl, inst = self._setup(game)
        assert impl.assign_direct(game.state, "test_investigator",
                                  horror=2) is True
        assert game.state.get_card_instance("utet_1") is None

    def test_assignment_capped_by_remaining_pool(self, game):
        """超过剩余承伤池的分配被拒绝（不部分吸收）。"""
        impl, inst = self._setup(game)
        assert impl.assign_direct(game.state, "test_investigator",
                                  damage=1) is True
        # 剩余生命1：再分配2伤害只吸收1 → 仍返回 True 并击败
        assert impl.assign_direct(game.state, "test_investigator",
                                  damage=2) is True
        # 已离场后不可再分配
        assert impl.assign_direct(game.state, "test_investigator",
                                  damage=1) is False


class TestVersatile:
    def test_deckbuilding_bonus(self, game):
        """+5牌组张数；追加任意职阶1张0级卡的构筑选项。"""
        impl = _register(game, Versatile)
        assert impl.deck_size_bonus(game.state, "test_investigator") == 5
        opts = impl.added_deckbuilding_options(game.state, "test_investigator")
        assert opts["count"] == 1
        assert opts["level"] == 0
        assert set(opts["classes"]) == {
            "guardian", "seeker", "rogue", "mystic", "survivor"}


class TestTheTowerXVI:
    def test_cannot_commit_while_in_hand(self, game):
        """高塔在手牌中：不能投入卡牌；不在手牌则无限制。"""
        impl = _register(game, TheTowerXVI)
        inv = game.state.get_investigator("test_investigator")

        assert impl.can_commit_cards(game.state, "test_investigator") is True
        inv.hand.append("the_tower_•_xvi_lv0")
        assert impl.can_commit_cards(game.state, "test_investigator") is False
        inv.hand.remove("the_tower_•_xvi_lv0")
        assert impl.can_commit_cards(game.state, "test_investigator") is True

    def test_cannot_replace_in_opening_hand(self, game):
        impl = _register(game, TheTowerXVI)
        assert impl.can_replace_in_opening_hand(
            game.state, "test_investigator") is False


class TestUnsolvedCase:
    def _setup(self, game):
        return _register(game, UnsolvedCase)

    def test_play_places_clue_on_highest_shroud(self, game):
        """打出：1个线索放到隐藏值最高的地点；记录移出游戏。"""
        impl = self._setup(game)
        loc_b = make_location_data(id="loc_b", shroud=4)
        game.register_card_data(loc_b)
        game.add_location("loc_b", loc_b)
        inv = game.state.get_investigator("test_investigator")
        inv.clues = 2

        _emit(game, GameEvent.CARD_PLAYED,
              extra={"card_id": "unsolved_case_lv0"})

        assert inv.clues == 1
        assert game.state.locations["loc_b"].clues == 1  # 隐藏值最高(4)
        assert game.state.locations["test_location"].clues == 3  # 未变
        assert "unsolved_case_lv0" in game.state.scenario.vars[
            "removed_from_game"]

    def test_play_without_clues(self, game):
        """没有线索时不放置，但仍移出游戏。"""
        impl = self._setup(game)
        inv = game.state.get_investigator("test_investigator")
        inv.clues = 0
        ctx = _emit(game, GameEvent.CARD_PLAYED,
                    extra={"card_id": "unsolved_case_lv0"})
        assert "unsolved_case_location" not in ctx.extra
        assert "unsolved_case_lv0" in game.state.scenario.vars[
            "removed_from_game"]

    def test_hunch_deck_intercept_and_game_end_penalty(self, game):
        """洗入直觉牌组改为加入威胁区域；游戏结束少获得2经验。"""
        impl = self._setup(game)
        inv = game.state.get_investigator("test_investigator")

        assert impl.on_shuffle_into_hunch_deck(
            game.state, "test_investigator") is True
        threat_cards = [
            game.state.get_card_instance(i).card_id for i in inv.threat_area]
        assert "unsolved_case_lv0" in threat_cards

        msg = impl.game_end_penalty(game.state, "test_investigator")
        assert msg is not None
        assert game.state.scenario.vars["xp_modifiers"][
            "test_investigator"] == -2


class TestWhispersFromTheDeep:
    def test_committed_icons_subtract(self, game):
        """投入本卡：其图标从技能值中减去而非增加（净 -1）。"""
        game.register_card_data(CardData(
            id="whispers_from_the_deep_lv0", name="Whispers from the Deep",
            name_cn="深海低语", type=CardType.SKILL,
            card_class=PlayerClass.NEUTRAL, skill_icons={"wild": 1},
        ))
        _register(game, WhispersFromTheDeep)
        inv = game.state.get_investigator("test_investigator")
        inv.hand.append("whispers_from_the_deep_lv0")
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]

        result = game.skill_test_engine.run_test(
            investigator_id="test_investigator",
            skill_type=Skill.INTELLECT,
            difficulty=3,
            committed_card_ids=["whispers_from_the_deep_lv0"],
            effect_card_ids=[],  # 弱点效果经 persistent_in_hand 注册强制生效
        )

        assert result.committed_icons == -1  # +1 被反转为 -1
        assert result.modified_skill == 2  # 3 - 1
        assert result.success is False

    def test_control_without_whispers(self, game):
        """对照：不投入本卡时检定正常（3 vs 3 成功）。"""
        _register(game, WhispersFromTheDeep)
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]

        result = game.skill_test_engine.run_test(
            investigator_id="test_investigator",
            skill_type=Skill.INTELLECT,
            difficulty=3,
        )
        assert result.success is True
