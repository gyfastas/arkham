"""Tests for Rite of Sanctification, Shield of Faith, Sacred Covenant.

成圣仪式(07019)：入场封印至多5祝福；同地点调查员打牌时消耗+释放1个减2费；
无封印标记则丢弃。
信仰之盾(07221)：入场封印至多5祝福；敌人攻击同地点调查员时消耗+释放1个
取消攻击；无封印标记则丢弃。
庄严圣约(07110)：消耗忽略本次检定揭示的祝福标记修正。
"""

import pytest

from backend.cards.guardian.rite_of_sanctification_lv0 import (
    RiteOfSanctification,
)
from backend.cards.guardian.sacred_covenant_lv2 import SacredCovenant
from backend.cards.guardian.shield_of_faith_lv2 import ShieldOfFaith
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import (
    CardType, ChaosTokenType, GameEvent, PlayerClass, Skill,
)
from backend.models.state import CardData, CardInstance
from backend.tests.conftest import (
    make_investigator_data, make_location_data,
)


def _game(extra_inv=False):
    g = Game("test")
    g.chaos_bag.seed(42)
    inv_data = make_investigator_data(willpower=3)
    g.register_card_data(inv_data)
    loc = make_location_data()
    g.register_card_data(loc)
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", g.state.get_card_data("test_location"))
    if extra_inv:
        g.add_investigator("inv2", inv_data, starting_location="test_location")
    g.chaos_bag.tokens = [ChaosTokenType.BLESS] * 5 + [ChaosTokenType.ZERO]
    return g


def _equip(game, card_id, impl_cls, iid="asset_1", inv_id="inv1"):
    game.register_card_data(CardData(
        id=card_id, name=card_id, name_cn=card_id, type=CardType.ASSET,
        card_class=PlayerClass.GUARDIAN, cost=2, traits=["blessed"],
    ))
    game.card_registry.register_class(impl_cls)
    inst = CardInstance(
        instance_id=iid, card_id=card_id,
        owner_id=inv_id, controller_id=inv_id,
    )
    game.state.cards_in_play[iid] = inst
    game.state.get_investigator(inv_id).play_area.append(iid)
    impl = game.card_registry.activate_card(
        card_id, iid, game.event_bus, chaos_bag=game.chaos_bag)
    game.event_bus.emit(EventContext(
        game_state=game.state, event=GameEvent.CARD_ENTERS_PLAY,
        investigator_id=inv_id, target=iid, extra={"card_id": card_id},
    ))
    return inst, impl


def _bless_in(lst):
    return sum(1 for t in lst if t == ChaosTokenType.BLESS)


class TestRiteOfSanctification:
    def test_seal_on_enter(self):
        """入场：从袋中封印5个祝福。"""
        game = _game()
        inst, impl = _equip(game, "rite_of_sanctification_lv0", RiteOfSanctification)
        assert _bless_in(game.chaos_bag.sealed) == 5
        assert _bless_in(game.chaos_bag.tokens) == 0

    def test_reduce_cost_on_card_played(self):
        """同地点调查员打牌：消耗+释放1封印，返还2资源；用尽后丢弃。"""
        game = _game(extra_inv=True)
        inst, impl = _equip(game, "rite_of_sanctification_lv0", RiteOfSanctification)
        inv2 = game.state.get_investigator("inv2")
        inv2.resources = 3

        ctx = EventContext(
            game_state=game.state, event=GameEvent.CARD_PLAYED,
            investigator_id="inv2", extra={"card_id": "some_event"},
        )
        game.event_bus.emit(ctx)

        assert inst.exhausted is True
        assert inv2.resources == 5  # 3 + 2 返还
        assert _bless_in(game.chaos_bag.sealed) == 4
        assert _bless_in(game.chaos_bag.tokens) == 1  # 释放回袋

    def test_discard_when_no_sealed_tokens(self):
        """袋中没有祝福可封印：入场即丢弃。"""
        game = _game()
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]
        inst, impl = _equip(game, "rite_of_sanctification_lv0", RiteOfSanctification)
        inv = game.state.get_investigator("inv1")
        assert "asset_1" not in inv.play_area
        assert game.state.get_card_instance("asset_1") is None


class TestShieldOfFaith:
    def test_cancel_attack_same_location(self):
        """敌人攻击同地点调查员：消耗+释放1封印，取消攻击。"""
        game = _game(extra_inv=True)
        inst, impl = _equip(game, "shield_of_faith_lv2", ShieldOfFaith)
        assert _bless_in(game.chaos_bag.sealed) == 5

        ctx = EventContext(
            game_state=game.state, event=GameEvent.ENEMY_ATTACKS,
            investigator_id="inv2", enemy_id="enemy_1",
        )
        game.event_bus.emit(ctx)

        assert ctx.cancelled is True
        assert inst.exhausted is True
        assert _bless_in(game.chaos_bag.sealed) == 4
        assert _bless_in(game.chaos_bag.tokens) == 1

    def test_no_cancel_other_location(self):
        """攻击其他地点的调查员：不触发。"""
        game = _game(extra_inv=True)
        other_loc = make_location_data(id="other_loc")
        game.register_card_data(other_loc)
        game.add_location("other_loc", other_loc)
        game.state.get_investigator("inv2").location_id = "other_loc"
        inst, impl = _equip(game, "shield_of_faith_lv2", ShieldOfFaith)

        ctx = EventContext(
            game_state=game.state, event=GameEvent.ENEMY_ATTACKS,
            investigator_id="inv2", enemy_id="enemy_1",
        )
        game.event_bus.emit(ctx)

        assert ctx.cancelled is False
        assert inst.exhausted is False

    def test_discard_after_last_token_released(self):
        """释放最后一个封印标记后丢弃（逐次消耗至0）。"""
        game = _game()
        game.chaos_bag.tokens = [ChaosTokenType.BLESS, ChaosTokenType.ZERO]
        inst, impl = _equip(game, "shield_of_faith_lv2", ShieldOfFaith)
        assert _bless_in(game.chaos_bag.sealed) == 1

        inst.exhausted = False
        ctx = EventContext(
            game_state=game.state, event=GameEvent.ENEMY_ATTACKS,
            investigator_id="inv1", enemy_id="enemy_1",
        )
        game.event_bus.emit(ctx)
        assert ctx.cancelled is True

        # 释放后无封印标记：已丢弃离场
        inv = game.state.get_investigator("inv1")
        assert "asset_1" not in inv.play_area  # 上一次释放后已丢弃


class TestSacredCovenant:
    def test_armed_ignores_bless_modifier(self):
        """武装后：祝福标记+2被忽略（3意志 vs 难度4 → 失败）。"""
        game = _game()
        game.chaos_bag.tokens = [ChaosTokenType.BLESS]
        inst, impl = _equip(game, "sacred_covenant_lv2", SacredCovenant)

        assert impl.arm(game.state, "inv1") is True
        result = game.skill_test_engine.run_test(
            "inv1", Skill.WILLPOWER, difficulty=4,
        )
        assert result.token_modifier == 0
        assert result.success is False
        assert inst.exhausted is True

    def test_unarmed_bless_applies(self):
        """未武装：祝福+2正常生效（3+2=5 ≥ 4 成功）。"""
        game = _game()
        game.chaos_bag.tokens = [ChaosTokenType.BLESS]
        inst, impl = _equip(game, "sacred_covenant_lv2", SacredCovenant)

        result = game.skill_test_engine.run_test(
            "inv1", Skill.WILLPOWER, difficulty=4,
        )
        assert result.token_modifier == 2
        assert result.success is True
        assert inst.exhausted is False
