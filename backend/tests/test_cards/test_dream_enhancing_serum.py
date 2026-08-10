"""Tests for Dream-Enhancing Serum (Level 0). (06159)

每种卡仅第一份副本计入手牌上限；抽到已有副本的牌后横置抽1张。
"""

import pytest

from backend.cards.seeker.dream_enhancing_serum_lv0 import DreamEnhancingSerum
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, ScenarioState,
)
from backend.tests.conftest import make_asset_data, make_investigator_data, make_skill_data


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
    # 同名两副本（不同 id）
    state.card_database["guts_a"] = make_skill_data(id="guts_a", name="Guts")
    state.card_database["guts_b"] = make_skill_data(id="guts_b", name="Guts")
    state.card_database["deduction"] = make_skill_data(
        id="deduction", name="Deduction")
    state.card_database["extra"] = make_skill_data(id="extra", name="Extra")

    state.card_database["dream_enhancing_serum_lv0"] = make_asset_data(
        id="dream_enhancing_serum_lv0", traits=["item", "science"])
    inst = CardInstance(
        instance_id="inst_serum", card_id="dream_enhancing_serum_lv0",
        owner_id="inv1", controller_id="inv1",
    )
    state.cards_in_play["inst_serum"] = inst
    inv.play_area.append("inst_serum")

    impl = DreamEnhancingSerum("inst_serum")
    impl.register(bus, "inst_serum")
    return state, bus, inv, inst, impl


class TestHandLimit:
    def test_duplicate_copies_dont_count(self, setup):
        """手牌上限 +重复副本数（2份 Guts 只计1份）。"""
        state, bus, inv, inst, impl = setup
        inv.hand = ["guts_a", "guts_b", "deduction"]
        ctx = EventContext(
            game_state=state, event=GameEvent.UPKEEP_PHASE_BEGINS,
            investigator_id="inv1", amount=8,
        )
        bus.emit(ctx)
        assert ctx.amount == 9  # 8 + 1个重复副本

    def test_no_duplicates_no_change(self, setup):
        state, bus, inv, inst, impl = setup
        inv.hand = ["guts_a", "deduction"]
        ctx = EventContext(
            game_state=state, event=GameEvent.UPKEEP_PHASE_BEGINS,
            investigator_id="inv1", amount=8,
        )
        bus.emit(ctx)
        assert ctx.amount == 8


class TestDuplicateDraw:
    def test_draw_duplicate_exhausts_and_draws(self, setup):
        """抽到已有副本的牌：横置并补抽1张。"""
        state, bus, inv, inst, impl = setup
        inv.hand = ["guts_a", "deduction", "guts_b"]  # guts_b 为刚抽到的
        inv.deck = ["extra"]
        ctx = EventContext(
            game_state=state, event=GameEvent.CARD_DRAWN,
            investigator_id="inv1", extra={"card_id": "guts_b"},
        )
        bus.emit(ctx)
        assert inst.exhausted is True
        assert "extra" in inv.hand

    def test_no_duplicate_no_trigger(self, setup):
        state, bus, inv, inst, impl = setup
        inv.hand = ["guts_a", "deduction"]
        bus.emit(EventContext(
            game_state=state, event=GameEvent.CARD_DRAWN,
            investigator_id="inv1", extra={"card_id": "deduction"},
        ))
        assert inst.exhausted is False
