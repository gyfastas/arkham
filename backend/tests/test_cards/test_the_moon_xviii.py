"""Tests for The Moon • XVIII (Level 1)."""

import importlib

import pytest

from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent, Skill
from backend.models.state import GameState, InvestigatorState, ScenarioState
from backend.tests.conftest import make_investigator_data

_mod = importlib.import_module("backend.cards.rogue.the_moon_•_xviii_lv1")
TheMoonXVIII = _mod.TheMoonXVIII
CARD_ID = "the_moon_•_xviii_lv1"


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()
    inv_data = make_investigator_data(agility=3)
    state.card_database[inv_data.id] = inv_data
    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1")
    state.investigators["inv1"] = inv
    return state, bus, inv


class TestTheMoonXVIII:
    def test_agility_bonus_in_play(self, setup):
        state, bus, inv = setup
        impl = TheMoonXVIII("moon_inst")
        impl.register(bus, "moon_inst")
        inv.hand.append(CARD_ID)
        assert impl.put_into_play_at_game_begin(state, "inv1") is True
        assert CARD_ID not in inv.hand
        inst_id = inv.play_area[0]
        # 重新绑定到真实实例 id（游戏开始入场由会话层创建实例）
        impl2 = TheMoonXVIII(inst_id)
        impl2.register(bus, inst_id)

        ctx = EventContext(
            game_state=state,
            event=GameEvent.SKILL_VALUE_DETERMINED,
            investigator_id="inv1",
            skill_type=Skill.AGILITY,
            amount=3,
        )
        bus.emit(ctx)
        assert ctx.amount == 4

    def test_no_bonus_for_other_skills(self, setup):
        state, bus, inv = setup
        impl = TheMoonXVIII("moon_inst")
        impl.register(bus, "moon_inst")
        inv.hand.append(CARD_ID)
        impl.put_into_play_at_game_begin(state, "inv1")
        impl.unregister(bus)
        impl2 = TheMoonXVIII(inv.play_area[0])
        impl2.register(bus, inv.play_area[0])

        ctx = EventContext(
            game_state=state,
            event=GameEvent.SKILL_VALUE_DETERMINED,
            investigator_id="inv1",
            skill_type=Skill.COMBAT,
            amount=3,
        )
        bus.emit(ctx)
        assert ctx.amount == 3

    def test_put_into_play_requires_in_hand(self, setup):
        state, bus, inv = setup
        impl = TheMoonXVIII("moon_inst")
        assert impl.put_into_play_at_game_begin(state, "inv1") is False
        assert inv.play_area == []
