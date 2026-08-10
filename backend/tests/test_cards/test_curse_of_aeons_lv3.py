"""Tests for Curse of Aeons (Level 3). (07195)

[reaction]你所在地点单次检定揭示第二个[curse]时，消耗本卡：取消该标记并
视为[skull]；检定结束后自动将两个[curse]移出混乱袋。
"""

import pytest
from backend.cards.mystic.curse_of_aeons_lv3 import CurseOfAeons
from backend.engine.event_bus import EventBus, EventContext
from backend.models.chaos import ChaosBag
from backend.models.enums import ChaosTokenType, GameEvent
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, ScenarioState,
)
from backend.tests.conftest import make_asset_data, make_investigator_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()
    inv_data = make_investigator_data()
    state.card_database[inv_data.id] = inv_data
    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1",
    )
    state.investigators["inv1"] = inv
    state.card_database["curse_of_aeons_lv3"] = make_asset_data(
        id="curse_of_aeons_lv3", name="Curse of Aeons",
        traits=["ritual", "cursed"],
    )
    inst = CardInstance(
        instance_id="inst_coa", card_id="curse_of_aeons_lv3",
        owner_id="inv1", controller_id="inv1",
    )
    state.cards_in_play["inst_coa"] = inst
    inv.play_area.append("inst_coa")
    impl = CurseOfAeons("inst_coa")
    impl.register(bus, "inst_coa")
    return state, bus, inv, inst, impl


def _curse_ctx(state):
    return EventContext(
        game_state=state, event=GameEvent.CHAOS_TOKEN_RESOLVED,
        investigator_id="inv1", chaos_token=ChaosTokenType.CURSE, amount=-2,
    )


class TestCurseOfAeons:
    def test_second_curse_cancelled_as_skull(self, setup):
        """第二个[curse]：消耗本卡，修正从-2清零（视为[skull]）。"""
        state, bus, inv, inst, impl = setup
        bus.emit(EventContext(
            game_state=state, event=GameEvent.SKILL_TEST_BEGINS,
            investigator_id="inv1",
        ))
        first = _curse_ctx(state)
        bus.emit(first)
        assert first.chaos_token == ChaosTokenType.CURSE  # 第一个不动
        assert inst.exhausted is False

        second = _curse_ctx(state)
        bus.emit(second)
        assert second.chaos_token == ChaosTokenType.SKULL
        assert second.amount == 0
        assert inst.exhausted is True
        assert second.extra["curse_of_aeons_triggered"] is True

    def test_removes_both_curses_after_test(self, setup):
        """检定结束：自动从袋中移除两个[curse]。"""
        state, bus, inv, inst, impl = setup
        bag = ChaosBag(tokens=[
            ChaosTokenType.CURSE, ChaosTokenType.CURSE, ChaosTokenType.ZERO])
        impl.bind_chaos_bag(bag)
        bus.emit(EventContext(
            game_state=state, event=GameEvent.SKILL_TEST_BEGINS,
            investigator_id="inv1",
        ))
        bus.emit(_curse_ctx(state))
        bus.emit(_curse_ctx(state))
        ctx = EventContext(
            game_state=state, event=GameEvent.SKILL_TEST_ENDS,
            investigator_id="inv1", success=True,
        )
        bus.emit(ctx)
        assert bag.tokens == [ChaosTokenType.ZERO]
        assert ctx.extra["curse_of_aeons_removed"] == 2

    def test_no_trigger_when_exhausted(self, setup):
        state, bus, inv, inst, impl = setup
        inst.exhausted = True
        bus.emit(EventContext(
            game_state=state, event=GameEvent.SKILL_TEST_BEGINS,
            investigator_id="inv1",
        ))
        bus.emit(_curse_ctx(state))
        ctx = _curse_ctx(state)
        bus.emit(ctx)
        assert ctx.chaos_token == ChaosTokenType.CURSE
        assert ctx.amount == -2

    def test_count_resets_between_tests(self, setup):
        """单次检定计数：跨检定的两个[curse]不触发。"""
        state, bus, inv, inst, impl = setup
        bus.emit(EventContext(
            game_state=state, event=GameEvent.SKILL_TEST_BEGINS,
            investigator_id="inv1",
        ))
        bus.emit(_curse_ctx(state))
        bus.emit(EventContext(
            game_state=state, event=GameEvent.SKILL_TEST_ENDS,
            investigator_id="inv1",
        ))
        bus.emit(EventContext(
            game_state=state, event=GameEvent.SKILL_TEST_BEGINS,
            investigator_id="inv1",
        ))
        ctx = _curse_ctx(state)
        bus.emit(ctx)
        assert ctx.chaos_token == ChaosTokenType.CURSE
        assert inst.exhausted is False
