"""Tests for Inquiring Mind (Level 0)."""

import pytest
from backend.cards.seeker.inquiring_mind_lv0 import InquiringMind
from backend.engine.event_bus import EventBus
from backend.models.state import (
    GameState, InvestigatorState, LocationState, ScenarioState,
)
from backend.tests.conftest import make_investigator_data, make_location_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()

    inv_data = make_investigator_data()
    state.card_database[inv_data.id] = inv_data
    loc_data = make_location_data()
    state.card_database[loc_data.id] = loc_data

    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="test_location",
    )
    state.investigators["inv1"] = inv
    loc = LocationState(location_id="test_location", card_data=loc_data, clues=2)
    state.locations["test_location"] = loc

    impl = InquiringMind("inquiring_inst")
    impl.register(bus, "inquiring_inst")
    return state, bus, inv, loc, impl


class TestInquiringMind:
    def test_card_data(self, setup):
        """InquiringMind card_id is correct and provides 3 wild icons."""
        state, bus, inv, loc, impl = setup
        assert impl.card_id == "inquiring_mind_lv0"
        # 3 wild icons come from card data JSON; no +2 handler exists.

    def test_no_skill_bonus_handler(self, setup):
        """提交后不给任何加值 handler（图标由数据自动结算）。"""
        from backend.models.enums import GameEvent, Skill
        from backend.engine.event_bus import EventContext
        state, bus, inv, loc, impl = setup
        ctx = EventContext(
            game_state=state, event=GameEvent.SKILL_VALUE_DETERMINED,
            investigator_id="inv1", skill_type=Skill.INTELLECT, amount=3,
            committed_cards=["inquiring_mind_lv0"],
        )
        bus.emit(ctx)
        assert ctx.amount == 3  # 无额外 +2

    def test_can_commit_with_clues(self, setup):
        """官方投入限制：所在地点有线索时可投入。"""
        state, bus, inv, loc, impl = setup
        assert impl.can_commit(state, "inv1") is True

    def test_cannot_commit_without_clues(self, setup):
        """所在地点没有线索时不可投入。"""
        state, bus, inv, loc, impl = setup
        loc.clues = 0
        assert impl.can_commit(state, "inv1") is False
