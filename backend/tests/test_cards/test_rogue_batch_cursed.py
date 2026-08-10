"""Behavior tests for the rogue bless/curse batch:
Eye of the Djinn (2), False Covenant (2), Faustian Bargain (0), Geas (2),
"Hit me!" (0), Justify the Means (3), Lucky Dice (3), "Lucky" Penny (2).
"""

import pytest

from backend.cards.rogue.eye_of_the_djinn_lv2 import EyeOfTheDjinn
from backend.cards.rogue.false_covenant_lv2 import FalseCovenant
from backend.cards.rogue.faustian_bargain_lv0 import FaustianBargain
from backend.cards.rogue.geas_lv2 import Geas
from backend.cards.rogue.hit_me_lv0 import HitMe
from backend.cards.rogue.justify_the_means_lv3 import JustifyTheMeans
from backend.cards.rogue.lucky_dice_lv3 import LuckyDice
from backend.cards.rogue.lucky_penny_lv2 import LuckyPenny
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import (
    Action, ChaosTokenType, GameEvent, PlayerClass, Skill,
)
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_asset_data, make_event_data, make_investigator_data,
    make_location_data, make_skill_data,
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


class TestEyeOfTheDjinn:
    def test_base_skill_set_to_5(self):
        """武装后检定基础技能值视为5（战斗3 vs 难度4，0标记→成功）。"""
        g = _game(combat=3)
        impl, iid = _equip(g, "eye_of_the_djinn_lv2", EyeOfTheDjinn)
        _emit(g, GameEvent.INVESTIGATOR_TURN_BEGINS, investigator_id="inv1")
        assert impl.activate(g.state, "inv1") is True
        assert g.state.get_card_instance(iid).exhausted is True

        g.chaos_bag.tokens = [ChaosTokenType.ZERO]
        result = g.skill_test_engine.run_test("inv1", Skill.COMBAT, 4)
        assert result.base_skill == 3
        assert result.modified_skill == 5
        assert result.success is True

    def test_bless_readies_and_curse_grants_action(self):
        """揭示[bless]：准备本卡；揭示[curse]：本回合+1行动。"""
        g = _game(combat=5)
        impl, iid = _equip(g, "eye_of_the_djinn_lv2", EyeOfTheDjinn)
        _emit(g, GameEvent.INVESTIGATOR_TURN_BEGINS, investigator_id="inv1")

        g.chaos_bag.tokens = [ChaosTokenType.BLESS]
        assert impl.activate(g.state, "inv1") is True
        g.skill_test_engine.run_test("inv1", Skill.COMBAT, 3)
        assert g.state.get_card_instance(iid).exhausted is False  # 已准备

        inv = g.state.get_investigator("inv1")
        inv.actions_remaining = 1
        g.chaos_bag.tokens = [ChaosTokenType.CURSE]
        assert impl.activate(g.state, "inv1") is True
        g.skill_test_engine.run_test("inv1", Skill.COMBAT, 3)
        assert inv.actions_remaining == 2  # +1额外行动

    def test_not_usable_outside_own_turn(self):
        g = _game()
        impl, iid = _equip(g, "eye_of_the_djinn_lv2", EyeOfTheDjinn)
        assert impl.activate(g.state, "inv1") is False


class TestFalseCovenant:
    def test_curse_cancelled_and_redrawn(self):
        """同地点调查员揭示[curse]：消耗本卡，取消并重抽（[0]修正归0）。"""
        g = _game()
        impl, iid = _equip(g, "false_covenant_lv2", FalseCovenant)
        g.chaos_bag.tokens = [ChaosTokenType.ZERO]
        ctx = _emit(
            g, GameEvent.CHAOS_TOKEN_RESOLVED, investigator_id="inv1",
            chaos_token=ChaosTokenType.CURSE, amount=-2)
        assert ctx.chaos_token == ChaosTokenType.ZERO
        assert ctx.amount == 0
        assert ctx.extra["false_covenant_redrawn"] == "0"
        assert g.state.get_card_instance(iid).exhausted is True

    def test_no_trigger_for_other_location(self):
        """不同地点的调查员揭示[curse]时不触发。"""
        g = _game()
        other_data = make_investigator_data(id="inv2")
        g.register_card_data(other_data)
        loc2 = make_location_data(id="loc2")
        g.register_card_data(loc2)
        g.add_investigator("inv2", other_data, starting_location="loc2")
        g.add_location("loc2", loc2, clues=0)
        impl, iid = _equip(g, "false_covenant_lv2", FalseCovenant)  # 持有者在 loc1
        g.chaos_bag.tokens = [ChaosTokenType.ZERO]
        ctx = _emit(
            g, GameEvent.CHAOS_TOKEN_RESOLVED, investigator_id="inv2",
            chaos_token=ChaosTokenType.CURSE, amount=-2)
        assert ctx.chaos_token == ChaosTokenType.CURSE  # 未取消
        assert g.state.get_card_instance(iid).exhausted is False


class TestFaustianBargain:
    def test_play_adds_curses_and_resources(self):
        """打出：混沌袋+2[curse]，打出者+5资源（引擎完整打出流程）。"""
        g = _game()
        g.card_registry.register_class(FaustianBargain)
        g.register_card_data(make_event_data(id="faustian_bargain_lv0", cost=0))
        inv = g.state.get_investigator("inv1")
        inv.hand = ["faustian_bargain_lv0"]
        inv.resources = 1
        before = len(g.chaos_bag.tokens)
        ok = g.action_resolver.perform_action(
            "inv1", Action.PLAY, card_id="faustian_bargain_lv0")
        assert ok is True
        assert inv.resources == 6
        assert g.chaos_bag.tokens.count(ChaosTokenType.CURSE) == 2
        assert len(g.chaos_bag.tokens) == before + 2


class TestGeas:
    def test_passive_plus_one_all_skills(self):
        """在场：全技能+1。"""
        g = _game(combat=3)
        impl, iid = _equip(g, "geas_lv2", Geas)
        g.chaos_bag.tokens = [ChaosTokenType.ZERO]
        result = g.skill_test_engine.run_test("inv1", Skill.COMBAT, 4)
        assert result.modified_skill == 4
        assert result.success is True

    def test_broken_play_promise_discards_and_curses(self):
        """诺言"不打出卡牌"被打破：弃置誓约，混沌袋+10[curse]。"""
        g = _game()
        impl, iid = _equip(g, "geas_lv2", Geas)
        _emit(g, GameEvent.CARD_ENTERS_PLAY, investigator_id="inv1",
              target=iid, extra={"card_id": "geas_lv2"})
        assert impl._promise == "play"
        _emit(g, GameEvent.INVESTIGATOR_TURN_BEGINS, investigator_id="inv1")
        ctx = _emit(g, GameEvent.CARD_PLAYED, investigator_id="inv1",
                    extra={"card_id": "some_event"})
        inv = g.state.get_investigator("inv1")
        assert iid not in inv.play_area
        assert "geas_lv2" in inv.discard
        assert g.chaos_bag.tokens.count(ChaosTokenType.CURSE) == 10
        assert ctx.extra["geas_broken"] is True

    def test_draw_promise_only_watches_draws(self):
        """诺言"不抽牌"：打出卡牌不违背，抽牌违背。"""
        g = _game()
        impl, iid = _equip(g, "geas_lv2", Geas)
        assert impl.choose_promise(g.state, "inv1", "draw") is True
        _emit(g, GameEvent.INVESTIGATOR_TURN_BEGINS, investigator_id="inv1")
        _emit(g, GameEvent.CARD_PLAYED, investigator_id="inv1",
              extra={"card_id": "some_event"})
        inv = g.state.get_investigator("inv1")
        assert iid in inv.play_area  # 打出不违背"不抽牌"
        _emit(g, GameEvent.CARD_DRAWN, investigator_id="inv1",
              extra={"card_id": "some_card"})
        assert iid not in inv.play_area
        assert "geas_lv2" in inv.discard


class TestHitMe:
    def _hand_setup(self, tokens):
        g = _game()
        g.card_registry.register_class(HitMe)
        g.register_card_data(make_event_data(id="hit_me_lv0", cost=1, fast=True))
        inv = g.state.get_investigator("inv1")
        inv.hand = ["hit_me_lv0"]
        inv.resources = 3
        impl = g.card_registry.activate_card(
            "hit_me_lv0", "hit_me_tmp", g.event_bus, chaos_bag=g.chaos_bag)
        g.chaos_bag.tokens = tokens
        return g, inv

    def test_negative_token_flipped_to_positive(self):
        """落后时自动打出：额外标记[-3]→+3（总修正 -1+3=2）。"""
        g, inv = self._hand_setup([ChaosTokenType.MINUS_3])
        ctx = _emit(
            g, GameEvent.CHAOS_TOKEN_RESOLVED, investigator_id="inv1",
            chaos_token=ChaosTokenType.MINUS_1, amount=-1)
        assert ctx.amount == 2
        assert ctx.extra["hit_me_token"] == "-3"
        assert "hit_me_lv0" not in inv.hand
        assert "hit_me_lv0" in inv.discard
        assert inv.resources == 2

    def test_skull_means_auto_fail(self):
        """额外标记为[skull]：自动失败。"""
        g, inv = self._hand_setup([ChaosTokenType.SKULL])
        ctx = _emit(
            g, GameEvent.CHAOS_TOKEN_RESOLVED, investigator_id="inv1",
            chaos_token=ChaosTokenType.MINUS_1, amount=-1)
        assert ctx.extra["force_auto_fail"] is True

    def test_no_auto_play_when_ahead(self):
        """当前修正非负时不自动打出。"""
        g, inv = self._hand_setup([ChaosTokenType.MINUS_3])
        ctx = _emit(
            g, GameEvent.CHAOS_TOKEN_RESOLVED, investigator_id="inv1",
            chaos_token=ChaosTokenType.PLUS_1, amount=1)
        assert ctx.amount == 1
        assert "hit_me_lv0" in inv.hand


class TestJustifyTheMeans:
    def test_commit_adds_curses_and_auto_succeeds(self):
        """投入：加入难度数量的[curse]；失败被翻转为自动成功。"""
        g = _game()
        g.card_registry.register_class(JustifyTheMeans)
        g.register_card_data(make_skill_data(id="justify_the_means_lv3",
                                             skill_icons={}))
        impl = g.card_registry.activate_card(
            "justify_the_means_lv3", "jtm_tmp", g.event_bus,
            chaos_bag=g.chaos_bag)
        commit = _emit(
            g, GameEvent.SKILL_TEST_COMMIT, investigator_id="inv1",
            skill_type=Skill.COMBAT, difficulty=4,
            committed_cards=["justify_the_means_lv3"], amount=0)
        assert commit.extra["justify_the_means_curses"] == 4
        assert g.chaos_bag.tokens.count(ChaosTokenType.CURSE) == 4

        failed = _emit(
            g, GameEvent.SKILL_TEST_FAILED, investigator_id="inv1",
            skill_type=Skill.COMBAT, success=False,
            modified_skill=2, difficulty=4)
        assert failed.success is True
        assert failed.extra["justify_the_means_auto_success"] is True


class TestLuckyDice:
    def test_reroll_replaces_token(self):
        """揭示[-2]：袋+1[curse]，重抽为[0]（修正归0），本卡留在场。"""
        g = _game()
        impl, iid = _equip(g, "lucky_dice_lv3", LuckyDice)
        g.chaos_bag.tokens = [ChaosTokenType.ZERO]
        ctx = _emit(
            g, GameEvent.CHAOS_TOKEN_RESOLVED, investigator_id="inv1",
            chaos_token=ChaosTokenType.MINUS_2, amount=-2)
        assert ctx.chaos_token == ChaosTokenType.ZERO
        assert ctx.amount == 0
        assert ctx.extra["lucky_dice_rerolled"] == "0"
        assert g.chaos_bag.tokens.count(ChaosTokenType.CURSE) == 1
        inv = g.state.get_investigator("inv1")
        assert iid in inv.play_area

    def test_reroll_into_curse_returns_to_hand(self):
        """重抽出[curse]：本卡返回手牌（不进弃牌堆）。"""
        g = _game()
        impl, iid = _equip(g, "lucky_dice_lv3", LuckyDice)
        g.chaos_bag.tokens = [ChaosTokenType.CURSE]
        ctx = _emit(
            g, GameEvent.CHAOS_TOKEN_RESOLVED, investigator_id="inv1",
            chaos_token=ChaosTokenType.MINUS_2, amount=-2)
        assert ctx.chaos_token == ChaosTokenType.CURSE
        assert ctx.amount == -2
        inv = g.state.get_investigator("inv1")
        assert iid not in inv.play_area
        assert "lucky_dice_lv3" in inv.hand
        assert "lucky_dice_lv3" not in inv.discard
        assert ctx.extra["lucky_dice_returned"] is True


class _StubRng:
    def __init__(self, value):
        self._value = value

    def random(self):
        return self._value


class TestLuckyPenny:
    def test_tails_treats_bless_as_curse_and_draws(self):
        """反面：[bless]视为[curse]（+2→-2），抽1张牌。"""
        g = _game()
        impl, iid = _equip(g, "lucky_penny_lv2", LuckyPenny)
        impl._rng = _StubRng(0.9)  # 反面
        inv = g.state.get_investigator("inv1")
        inv.deck = ["some_card"]
        ctx = _emit(
            g, GameEvent.CHAOS_TOKEN_RESOLVED, investigator_id="inv1",
            chaos_token=ChaosTokenType.BLESS, amount=2)
        assert ctx.chaos_token == ChaosTokenType.CURSE
        assert ctx.amount == -2
        assert ctx.extra["lucky_penny_treated_as"] == "curse"
        assert inv.hand == ["some_card"]

    def test_heads_treats_curse_as_bless(self):
        """正面：[curse]视为[bless]（-2→+2），不抽牌。"""
        g = _game()
        impl, iid = _equip(g, "lucky_penny_lv2", LuckyPenny)
        impl._rng = _StubRng(0.1)  # 正面
        inv = g.state.get_investigator("inv1")
        inv.deck = ["some_card"]
        ctx = _emit(
            g, GameEvent.CHAOS_TOKEN_RESOLVED, investigator_id="inv1",
            chaos_token=ChaosTokenType.CURSE, amount=-2)
        assert ctx.chaos_token == ChaosTokenType.BLESS
        assert ctx.amount == 2
        assert inv.hand == []
