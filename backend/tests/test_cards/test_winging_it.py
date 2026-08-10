"""Tests for Winging It (Level 0)."""

import pytest
from backend.cards.survivor.winging_it_lv0 import WingingIt
from backend.engine.event_bus import EventBus, EventContext
from backend.engine.skill_test import SkillTestEngine
from backend.models.chaos import ChaosBag
from backend.models.enums import ChaosTokenType, GameEvent, Skill
from backend.models.state import GameState, InvestigatorState, LocationState, ScenarioState
from backend.tests.conftest import make_investigator_data, make_location_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()
    bag = ChaosBag()
    bag.seed(42)

    inv_data = make_investigator_data(intellect=3)
    state.card_database[inv_data.id] = inv_data
    loc_data = make_location_data(shroud=3)
    state.card_database[loc_data.id] = loc_data

    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data,
        location_id="test_location", deck=["deck_card"],
    )
    state.investigators["inv1"] = inv
    state.locations["test_location"] = LocationState(
        location_id="test_location", card_data=loc_data, clues=3)

    engine = SkillTestEngine(state, bus, bag)
    impl = WingingIt("wi_inst")
    impl.register(bus, "wi_inst")
    return state, bus, bag, engine, inv, impl


def _play(bus, state, **extra):
    ctx = EventContext(
        game_state=state, event=GameEvent.CARD_PLAYED,
        investigator_id="inv1",
        extra={"card_id": "winging_it_lv0", **extra},
    )
    bus.emit(ctx)
    # 镜像引擎 _play_event：事件结算后入弃牌堆
    inv = state.get_investigator("inv1")
    inv.discard.append("winging_it_lv0")
    return ctx


def _investigate(engine, state, bus, inv):
    loc = state.get_location(inv.location_id)

    def on_success(_result):
        if loc.clues > 0:
            loc.clues -= 1
            inv.clues += 1
            bus.emit(EventContext(
                game_state=state, event=GameEvent.CLUE_DISCOVERED,
                investigator_id=inv.investigator_id,
                location_id=loc.location_id, amount=1,
            ))
    return engine.run_test(
        investigator_id="inv1", skill_type=Skill.INTELLECT,
        difficulty=loc.shroud, on_success=on_success,
    )


class TestWingingIt:
    def test_lowers_shroud_from_hand(self, setup):
        """从手牌打出：本次调查隐藏值-1（难度3→2），成功拿基础1条线索。"""
        state, bus, bag, engine, inv, impl = setup
        bag.tokens = [ChaosTokenType.ZERO]
        _play(bus, state)
        result = _investigate(engine, state, bus, inv)
        # 3 vs (3-1)=2 → 成功；非弃牌堆打出，无额外线索
        assert result.difficulty == 2
        assert result.success
        assert inv.clues == 1
        # 正常入弃牌堆，不洗回
        assert "winging_it_lv0" in inv.discard

    def test_from_discard_extra_clue_and_reshuffle(self, setup):
        """从弃牌堆打出：成功额外+1线索，结算后洗回牌堆。"""
        state, bus, bag, engine, inv, impl = setup
        bag.tokens = [ChaosTokenType.ZERO]
        _play(bus, state, from_discard_pile=True)
        result = _investigate(engine, state, bus, inv)
        assert result.success
        assert inv.clues == 2  # 基础1 + 额外1
        assert "winging_it_lv0" not in inv.discard
        assert "winging_it_lv0" in inv.deck

    def test_from_discard_failed_test_still_reshuffles(self, setup):
        """从弃牌堆打出但调查失败：无额外线索；洗回仍在检定结束时生效。"""
        state, bus, bag, engine, inv, impl = setup
        bag.tokens = [ChaosTokenType.AUTO_FAIL]
        _play(bus, state, from_discard_pile=True)
        result = _investigate(engine, state, bus, inv)
        assert not result.success
        assert inv.clues == 0
        assert "winging_it_lv0" in inv.deck

    def test_shroud_floor_at_zero(self, setup):
        """隐藏值-1 不会低于0。"""
        state, bus, bag, engine, inv, impl = setup
        state.get_location("test_location").card_data.shroud = 0
        bag.tokens = [ChaosTokenType.ZERO]
        _play(bus, state)
        result = _investigate(engine, state, bus, inv)
        assert result.difficulty == 0
        assert result.success
