"""Tests for Tristan Botley (Level 2)."""

import pytest

from backend.cards.rogue.tristan_botley_lv2 import TristanBotley
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import ChaosTokenType, GameEvent, Skill
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, ScenarioState,
)
from backend.tests.conftest import make_investigator_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()
    inv_data = make_investigator_data(willpower=2, intellect=4, combat=3, agility=1)
    state.card_database[inv_data.id] = inv_data
    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1")
    state.investigators["inv1"] = inv
    inst = CardInstance(
        instance_id="tristan_inst", card_id="tristan_botley_lv2",
        owner_id="inv1", controller_id="inv1",
    )
    state.cards_in_play["tristan_inst"] = inst
    inv.play_area.append("tristan_inst")
    impl = TristanBotley("tristan_inst")
    impl.register(bus, "tristan_inst")
    return state, bus, inv, impl


def _turn_begins(bus, state):
    ctx = EventContext(
        game_state=state,
        event=GameEvent.INVESTIGATOR_TURN_BEGINS,
        investigator_id="inv1",
    )
    bus.emit(ctx)
    return ctx


def _skill_value(bus, state, skill, amount):
    ctx = EventContext(
        game_state=state,
        event=GameEvent.SKILL_VALUE_DETERMINED,
        investigator_id="inv1",
        skill_type=skill,
        amount=amount,
    )
    bus.emit(ctx)
    return ctx


class TestTristanBotleySkillChoice:
    def test_chooses_two_highest_skills(self, setup):
        state, bus, inv, impl = setup
        ctx = _turn_begins(bus, state)
        # 智力4、战斗3 为基础值最高的两项
        assert set(ctx.extra["tristan_chosen"]) == {"intellect", "combat"}
        assert _skill_value(bus, state, Skill.INTELLECT, 4).amount == 5
        assert _skill_value(bus, state, Skill.COMBAT, 3).amount == 4
        assert _skill_value(bus, state, Skill.WILLPOWER, 2).amount == 2
        assert _skill_value(bus, state, Skill.AGILITY, 1).amount == 1

    def test_no_bonus_before_choice(self, setup):
        state, bus, inv, impl = setup
        assert _skill_value(bus, state, Skill.INTELLECT, 4).amount == 4


class TestTristanBotleyFreePlay:
    def test_three_bless_curse_tokens_play_free(self, setup):
        """检定中抽出3+祝福/诅咒标记后：从手牌免费入场。"""
        state, bus, inv, impl = setup
        inv.hand.append("tristan_botley_lv2")
        bus.emit(EventContext(
            game_state=state, event=GameEvent.SKILL_TEST_BEGINS,
            investigator_id="inv1", skill_type=Skill.WILLPOWER, difficulty=3,
        ))
        for _ in range(3):
            bus.emit(EventContext(
                game_state=state, event=GameEvent.CHAOS_TOKEN_REVEALED,
                investigator_id="inv1", chaos_token=ChaosTokenType.BLESS,
            ))
        ctx = EventContext(
            game_state=state, event=GameEvent.SKILL_TEST_ENDS,
            investigator_id="inv1", success=True,
        )
        bus.emit(ctx)
        new_id = ctx.extra["tristan_played_free"]
        assert "tristan_botley_lv2" not in inv.hand
        assert new_id in inv.play_area
        assert state.get_card_instance(new_id).card_id == "tristan_botley_lv2"

    def test_two_tokens_not_enough(self, setup):
        state, bus, inv, impl = setup
        inv.hand.append("tristan_botley_lv2")
        bus.emit(EventContext(
            game_state=state, event=GameEvent.SKILL_TEST_BEGINS,
            investigator_id="inv1", skill_type=Skill.WILLPOWER, difficulty=3,
        ))
        for _ in range(2):
            bus.emit(EventContext(
                game_state=state, event=GameEvent.CHAOS_TOKEN_REVEALED,
                investigator_id="inv1", chaos_token=ChaosTokenType.CURSE,
            ))
        ctx = EventContext(
            game_state=state, event=GameEvent.SKILL_TEST_ENDS,
            investigator_id="inv1", success=True,
        )
        bus.emit(ctx)
        assert "tristan_played_free" not in ctx.extra
        assert "tristan_botley_lv2" in inv.hand
