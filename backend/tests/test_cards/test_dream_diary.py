"""Tests for Dream Diary (Level 0 & 3). (06112 / 06238)

lv0：[行动]从绑定卡找梦的本质入手；投入梦的本质3+差值成功记录冒险日志。
lv3：回合开始自动找梦的本质入手；8+手牌时投入的梦的本质+2图标。
"""

import pytest

from backend.cards.seeker.dream_diary_lv0 import (
    CAMPAIGN_LOG_ENTRY, ESSENCE, SET_ASIDE_VAR, DreamDiary,
)
from backend.cards.seeker.dream_diary_lv3 import DreamDiaryLv3
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent, Skill
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, ScenarioState,
)
from backend.tests.conftest import (
    make_asset_data, make_investigator_data, make_skill_data,
)


def _base_state():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()
    inv_data = make_investigator_data()
    state.card_database[inv_data.id] = inv_data
    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1",
    )
    state.investigators["inv1"] = inv
    state.card_database[ESSENCE] = make_skill_data(
        id=ESSENCE, name="Essence of the Dream",
        skill_icons={"wild": 2})
    return state, bus, inv


def _place_diary(state, bus, inv, card_id, cls):
    state.card_database[card_id] = make_asset_data(
        id=card_id, traits=["item", "tome", "charm"])
    inst = CardInstance(
        instance_id=f"inst_{card_id}", card_id=card_id,
        owner_id="inv1", controller_id="inv1",
    )
    state.cards_in_play[inst.instance_id] = inst
    inv.play_area.append(inst.instance_id)
    impl = cls(inst.instance_id)
    impl.register(bus, inst.instance_id)
    return inst, impl


def _enter_play(state, bus, inst):
    bus.emit(EventContext(
        game_state=state, event=GameEvent.CARD_ENTERS_PLAY,
        investigator_id="inv1", target=inst.instance_id,
    ))


class TestDreamDiaryLv0:
    def test_activate_fetches_essence_from_bonded(self):
        """入场后绑定池有梦的本质；[行动]查找入手。"""
        state, bus, inv = _base_state()
        inst, impl = _place_diary(state, bus, inv, "dream_diary_lv0",
                                  DreamDiary)
        _enter_play(state, bus, inst)
        assert ESSENCE in state.scenario.vars[SET_ASIDE_VAR]

        assert impl.activate(state, "inv1") is True
        assert ESSENCE in inv.hand
        assert ESSENCE not in state.scenario.vars[SET_ASIDE_VAR]
        # 绑定池已空：再次查找失败
        assert impl.activate(state, "inv1") is False

    def test_success_by_3_records_campaign_log(self):
        state, bus, inv = _base_state()
        inst, impl = _place_diary(state, bus, inv, "dream_diary_lv0",
                                  DreamDiary)
        bus.emit(EventContext(
            game_state=state, event=GameEvent.SKILL_TEST_SUCCESSFUL,
            investigator_id="inv1", skill_type=Skill.WILLPOWER,
            modified_skill=7, difficulty=3, committed_cards=[ESSENCE],
        ))
        assert CAMPAIGN_LOG_ENTRY in state.scenario.vars["campaign_log"]

    def test_margin_below_3_no_record(self):
        state, bus, inv = _base_state()
        inst, impl = _place_diary(state, bus, inv, "dream_diary_lv0",
                                  DreamDiary)
        bus.emit(EventContext(
            game_state=state, event=GameEvent.SKILL_TEST_SUCCESSFUL,
            investigator_id="inv1", skill_type=Skill.WILLPOWER,
            modified_skill=5, difficulty=3, committed_cards=[ESSENCE],
        ))
        assert "campaign_log" not in state.scenario.vars


class TestDreamDiaryLv3:
    def test_turn_begins_fetches_essence(self):
        """你的回合开始：梦的本质自动入手。"""
        state, bus, inv = _base_state()
        inst, impl = _place_diary(state, bus, inv, "dream_diary_lv3",
                                  DreamDiaryLv3)
        _enter_play(state, bus, inst)
        bus.emit(EventContext(
            game_state=state, event=GameEvent.INVESTIGATOR_TURN_BEGINS,
            investigator_id="inv1",
        ))
        assert ESSENCE in inv.hand

    def test_essence_gains_two_wild_with_8_cards(self):
        """8+手牌时投入的梦的本质+2图标。"""
        state, bus, inv = _base_state()
        inst, impl = _place_diary(state, bus, inv, "dream_diary_lv3",
                                  DreamDiaryLv3)
        state.card_database["f"] = make_skill_data(id="f", name="f")
        inv.hand = [ESSENCE] + ["f"] * 7  # 8张
        ctx = EventContext(
            game_state=state, event=GameEvent.SKILL_TEST_COMMIT,
            investigator_id="inv1", skill_type=Skill.INTELLECT,
            committed_cards=[ESSENCE], amount=2,
        )
        bus.emit(ctx)
        assert ctx.amount == 4

    def test_below_8_cards_no_bonus(self):
        state, bus, inv = _base_state()
        inst, impl = _place_diary(state, bus, inv, "dream_diary_lv3",
                                  DreamDiaryLv3)
        inv.hand = [ESSENCE]
        ctx = EventContext(
            game_state=state, event=GameEvent.SKILL_TEST_COMMIT,
            investigator_id="inv1", skill_type=Skill.INTELLECT,
            committed_cards=[ESSENCE], amount=2,
        )
        bus.emit(ctx)
        assert ctx.amount == 2
