"""Tests for Cryptic Grimoire (Level 0 & 4). (07022 / 07192)

lv0：[行动]加诅咒；袋中10诅咒时[行动]丢弃本卡：5诅咒换5祝福+冒险日志。
lv4：结算诅咒放秘密；花5秘密把遭遇抽牌换成自己牌堆抽牌。
"""

import pytest

from backend.cards.seeker.cryptic_grimoire_lv0 import (
    CAMPAIGN_LOG_ENTRY, CrypticGrimoire,
)
from backend.cards.seeker.cryptic_grimoire_lv4 import CrypticGrimoireLv4
from backend.engine.event_bus import EventBus, EventContext
from backend.models.chaos import ChaosBag
from backend.models.enums import ChaosTokenType, GameEvent, Phase
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, ScenarioState,
)
from backend.tests.conftest import make_asset_data, make_investigator_data


def _base_state():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()
    inv_data = make_investigator_data()
    state.card_database[inv_data.id] = inv_data
    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1",
    )
    state.investigators["inv1"] = inv
    return state, bus, inv


def _place(state, bus, inv, card_id, cls, uses=None):
    state.card_database[card_id] = make_asset_data(
        id=card_id, traits=["item", "tome"])
    inst = CardInstance(
        instance_id=f"inst_{card_id}", card_id=card_id,
        owner_id="inv1", controller_id="inv1",
    )
    if uses:
        inst.uses = dict(uses)
    state.cards_in_play[inst.instance_id] = inst
    inv.play_area.append(inst.instance_id)
    impl = cls(inst.instance_id)
    impl.register(bus, inst.instance_id)
    return inst, impl


class TestCrypticGrimoireLv0:
    def test_add_curse_token(self):
        state, bus, inv = _base_state()
        inst, impl = _place(state, bus, inv, "cryptic_grimoire_lv0",
                            CrypticGrimoire)
        bag = ChaosBag(tokens=[ChaosTokenType.ZERO])
        impl.bind_chaos_bag(bag)
        assert impl.activate_curse(state, "inv1") is True
        assert bag.tokens.count(ChaosTokenType.CURSE) == 1

    def test_translate_replaces_curses_with_blesses(self):
        """袋中≥10诅咒：丢弃本卡，5诅咒换5祝福，记录冒险日志。"""
        state, bus, inv = _base_state()
        inst, impl = _place(state, bus, inv, "cryptic_grimoire_lv0",
                            CrypticGrimoire)
        bag = ChaosBag(tokens=[ChaosTokenType.ZERO]
                       + [ChaosTokenType.CURSE] * 10)
        impl.bind_chaos_bag(bag)
        assert impl.activate_translate(state, "inv1") is True
        assert bag.tokens.count(ChaosTokenType.CURSE) == 5
        assert bag.tokens.count(ChaosTokenType.BLESS) == 5
        assert inst.instance_id not in inv.play_area
        assert "cryptic_grimoire_lv0" in inv.discard
        assert CAMPAIGN_LOG_ENTRY in state.scenario.vars["campaign_log"]

    def test_translate_requires_10_curses(self):
        state, bus, inv = _base_state()
        inst, impl = _place(state, bus, inv, "cryptic_grimoire_lv0",
                            CrypticGrimoire)
        bag = ChaosBag(tokens=[ChaosTokenType.CURSE] * 9)
        impl.bind_chaos_bag(bag)
        assert impl.activate_translate(state, "inv1") is False
        assert inst.instance_id in inv.play_area


class TestCrypticGrimoireLv4:
    def test_curse_resolution_places_secret(self):
        state, bus, inv = _base_state()
        inst, impl = _place(state, bus, inv, "cryptic_grimoire_lv4",
                            CrypticGrimoireLv4)
        bus.emit(EventContext(
            game_state=state, event=GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="inv1", chaos_token=ChaosTokenType.CURSE,
            amount=-2,
        ))
        assert inst.uses["secrets"] == 1

    def test_replace_encounter_draw(self):
        """花5秘密：遭遇顶牌放回牌堆顶，改抽自己牌堆；弃牌堆重复记录被清理。"""
        state, bus, inv = _base_state()
        state.scenario.current_phase = Phase.MYTHOS
        inst, impl = _place(state, bus, inv, "cryptic_grimoire_lv4",
                            CrypticGrimoireLv4, uses={"secrets": 5})
        inv.deck = ["my_card"]
        state.scenario.encounter_deck = ["enc_a", "enc_b"]

        # 模拟 phase_mythos 流程：弹出顶牌 → 发事件 → 无条件放入弃牌堆
        drawn = state.scenario.encounter_deck.pop(0)
        ctx = EventContext(
            game_state=state, event=GameEvent.ENCOUNTER_CARD_DRAWN,
            investigator_id="inv1", extra={"card_id": drawn},
        )
        bus.emit(ctx)
        state.scenario.encounter_discard.append(drawn)  # 引擎无条件放入

        assert inst.uses["secrets"] == 0
        assert "my_card" in inv.hand
        # 遭遇牌回到牌堆顶（弃牌堆暂有重复记录）
        assert state.scenario.encounter_deck[0] == "enc_a"
        assert "enc_a" in state.scenario.encounter_discard
        # 阶段结束：重复记录被清理
        bus.emit(EventContext(
            game_state=state, event=GameEvent.MYTHOS_PHASE_ENDS))
        assert "enc_a" not in state.scenario.encounter_discard
        assert state.scenario.encounter_deck == ["enc_a", "enc_b"]

    def test_not_enough_secrets_no_replacement(self):
        state, bus, inv = _base_state()
        inst, impl = _place(state, bus, inv, "cryptic_grimoire_lv4",
                            CrypticGrimoireLv4, uses={"secrets": 4})
        inv.deck = ["my_card"]
        state.scenario.encounter_deck = ["enc_a"]
        drawn = state.scenario.encounter_deck.pop(0)
        bus.emit(EventContext(
            game_state=state, event=GameEvent.ENCOUNTER_CARD_DRAWN,
            investigator_id="inv1", extra={"card_id": drawn},
        ))
        assert "my_card" not in inv.hand
        assert state.scenario.encounter_deck == []
