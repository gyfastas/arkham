"""Tests for Seal of the Seventh Sign (lv5), Shards of the Void (lv3),
The Chthonian Stone (lv0) — 封印机制卡。"""

import pytest

from backend.cards.mystic.seal_of_the_seventh_sign_lv5 import SealOfTheSeventhSign
from backend.cards.mystic.shards_of_the_void_lv3 import ShardsOfTheVoid
from backend.cards.mystic.the_chthonian_stone_lv0 import TheChthonianStone
from backend.engine.event_bus import EventBus, EventContext
from backend.models.chaos import ChaosBag
from backend.models.enums import ChaosTokenType, GameEvent, Skill
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, ScenarioState,
)
from backend.tests.conftest import make_asset_data, make_investigator_data


def _setup(card_id, impl_cls, uses=None, willpower=5, combat=3):
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()
    bag = ChaosBag()
    bag.seed(42)

    inv_data = make_investigator_data(willpower=willpower, combat=combat)
    state.card_database[inv_data.id] = inv_data
    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1")
    state.investigators["inv1"] = inv

    state.card_database[card_id] = make_asset_data(id=card_id, uses=uses)
    inst = CardInstance(
        instance_id="inst1", card_id=card_id,
        owner_id="inv1", controller_id="inv1",
    )
    inst.uses = dict(uses or {})
    state.cards_in_play["inst1"] = inst
    inv.play_area.append("inst1")

    impl = impl_cls("inst1")
    impl.register(bus, "inst1")
    impl.bind_chaos_bag(bag)
    return state, bus, bag, inv, inst, impl


def _emit(bus, state, event, **kwargs):
    ctx = EventContext(game_state=state, event=event, investigator_id="inv1", **kwargs)
    bus.emit(ctx)
    return ctx


class TestSealOfTheSeventhSign:
    CID = "seal_of_the_seventh_sign_lv5"

    def test_seals_auto_fail_on_enter(self):
        state, bus, bag, inv, inst, impl = _setup(
            self.CID, SealOfTheSeventhSign, uses={"chargess": 7})
        assert ChaosTokenType.AUTO_FAIL in bag.tokens
        _emit(bus, state, GameEvent.CARD_ENTERS_PLAY, target="inst1",
              extra={"card_id": self.CID})
        assert ChaosTokenType.AUTO_FAIL not in bag.tokens
        assert ChaosTokenType.AUTO_FAIL in bag.sealed

    def test_symbol_token_removes_charge(self):
        state, bus, bag, inv, inst, impl = _setup(
            self.CID, SealOfTheSeventhSign, uses={"chargess": 7})
        _emit(bus, state, GameEvent.CARD_ENTERS_PLAY, target="inst1",
              extra={"card_id": self.CID})
        _emit(bus, state, GameEvent.CHAOS_TOKEN_RESOLVED,
              chaos_token=ChaosTokenType.SKULL)
        assert inst.uses["chargess"] == 6
        # 非符号标记不移除充能
        _emit(bus, state, GameEvent.CHAOS_TOKEN_RESOLVED,
              chaos_token=ChaosTokenType.MINUS_2)
        assert inst.uses["chargess"] == 6

    def test_removed_from_game_when_charges_empty(self):
        state, bus, bag, inv, inst, impl = _setup(
            self.CID, SealOfTheSeventhSign, uses={"chargess": 1})
        _emit(bus, state, GameEvent.CARD_ENTERS_PLAY, target="inst1",
              extra={"card_id": self.CID})
        _emit(bus, state, GameEvent.CHAOS_TOKEN_RESOLVED,
              chaos_token=ChaosTokenType.CULTIST)
        # 移出游戏：不在场上/弃牌堆，登记在 removed_from_game，封印归还袋中
        assert "inst1" not in state.cards_in_play
        assert "inst1" not in inv.play_area
        assert self.CID not in inv.discard
        assert self.CID in state.scenario.vars["removed_from_game"]
        assert ChaosTokenType.AUTO_FAIL in bag.tokens


class TestShardsOfTheVoid:
    CID = "shards_of_the_void_lv3"

    def test_seals_zero_on_enter(self):
        state, bus, bag, inv, inst, impl = _setup(
            self.CID, ShardsOfTheVoid, uses={"chargess": 3})
        zeros_before = bag.tokens.count(ChaosTokenType.ZERO)
        assert zeros_before > 0
        _emit(bus, state, GameEvent.CARD_ENTERS_PLAY, target="inst1",
              extra={"card_id": self.CID})
        assert bag.tokens.count(ChaosTokenType.ZERO) == zeros_before - 1
        assert impl._sealed == [ChaosTokenType.ZERO]

    def test_attack_willpower_plus_two_per_sealed_zero(self):
        """意志(5)代替战斗(3)，1个封印的0 → 再+2。"""
        state, bus, bag, inv, inst, impl = _setup(
            self.CID, ShardsOfTheVoid, uses={"chargess": 3})
        _emit(bus, state, GameEvent.CARD_ENTERS_PLAY, target="inst1",
              extra={"card_id": self.CID})
        assert impl.activate(state, "inv1") is True
        assert inst.uses["chargess"] == 2
        ctx = _emit(bus, state, GameEvent.SKILL_VALUE_DETERMINED,
                    skill_type=Skill.COMBAT, amount=3, source="inst1")
        assert ctx.amount == 7  # 5 意志 + 2（1个封印的0）

    def test_revealed_zero_sealed_and_bonus_damage(self):
        state, bus, bag, inv, inst, impl = _setup(
            self.CID, ShardsOfTheVoid, uses={"chargess": 3})
        _emit(bus, state, GameEvent.CARD_ENTERS_PLAY, target="inst1",
              extra={"card_id": self.CID})
        impl.activate(state, "inv1")
        _emit(bus, state, GameEvent.CHAOS_TOKEN_RESOLVED,
              chaos_token=ChaosTokenType.ZERO, source="inst1")
        assert impl._sealed.count(ChaosTokenType.ZERO) == 2
        ctx = _emit(bus, state, GameEvent.SKILL_TEST_SUCCESSFUL,
                    skill_type=Skill.COMBAT, success=True, source="inst1")
        # 基础+1伤害，揭示1个"0"再+1
        assert ctx.extra["bonus_damage"] == 2

    def test_release_sealed_zero_when_no_charges(self):
        state, bus, bag, inv, inst, impl = _setup(
            self.CID, ShardsOfTheVoid, uses={"chargess": 0})
        _emit(bus, state, GameEvent.CARD_ENTERS_PLAY, target="inst1",
              extra={"card_id": self.CID})
        tokens_before = len(bag.tokens)
        assert impl.activate(state, "inv1") is True
        assert impl._sealed == []
        assert len(bag.tokens) == tokens_before + 1  # 释放归还袋中


class TestTheChthonianStone:
    CID = "the_chthonian_stone_lv0"

    def test_seals_symbol_on_enter(self):
        state, bus, bag, inv, inst, impl = _setup(self.CID, TheChthonianStone)
        _emit(bus, state, GameEvent.CARD_ENTERS_PLAY, target="inst1",
              extra={"card_id": self.CID})
        assert impl._sealed == [ChaosTokenType.SKULL]  # 自动选第一个可用符号
        assert ChaosTokenType.SKULL in bag.sealed

    def test_return_to_hand_on_auto_fail(self):
        state, bus, bag, inv, inst, impl = _setup(self.CID, TheChthonianStone)
        _emit(bus, state, GameEvent.CARD_ENTERS_PLAY, target="inst1",
              extra={"card_id": self.CID})
        _emit(bus, state, GameEvent.CHAOS_TOKEN_RESOLVED,
              chaos_token=ChaosTokenType.AUTO_FAIL)
        assert "inst1" not in state.cards_in_play
        assert "inst1" not in inv.play_area
        assert self.CID in inv.hand
        # 封印归还
        assert ChaosTokenType.SKULL in bag.tokens
        assert impl._sealed == []

    def test_no_return_on_other_investigators_auto_fail(self):
        state, bus, bag, inv, inst, impl = _setup(self.CID, TheChthonianStone)
        _emit(bus, state, GameEvent.CARD_ENTERS_PLAY, target="inst1",
              extra={"card_id": self.CID})
        ctx = EventContext(
            game_state=state, event=GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="inv2", chaos_token=ChaosTokenType.AUTO_FAIL,
        )
        bus.emit(ctx)
        assert "inst1" in state.cards_in_play
