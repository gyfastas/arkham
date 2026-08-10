"""Tests for Empower Self (Level 2). (06243)

[fast]消耗：本次检定+2智力（一次）。在场时维护"忽略意志代替智力"标记
（scenario.vars，替换类效果可查询——通用拦截为引擎缺口）。
"""

import pytest
from backend.cards.mystic.empower_self_lv2 import EmpowerSelf
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent, Skill
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, ScenarioState,
)
from backend.tests.conftest import make_asset_data, make_investigator_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()
    inv_data = make_investigator_data(intellect=3)
    state.card_database[inv_data.id] = inv_data
    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1",
    )
    state.investigators["inv1"] = inv
    state.card_database["empower_self_lv2"] = make_asset_data(
        id="empower_self_lv2", name="Empower Self", traits=["ritual"])
    inst = CardInstance(
        instance_id="inst_emp", card_id="empower_self_lv2",
        owner_id="inv1", controller_id="inv1",
    )
    state.cards_in_play["inst_emp"] = inst
    inv.play_area.append("inst_emp")
    impl = EmpowerSelf("inst_emp")
    impl.register(bus, "inst_emp")
    return state, bus, inv, inst, impl


def _intellect_ctx(state, amount=3):
    return EventContext(
        game_state=state, event=GameEvent.SKILL_VALUE_DETERMINED,
        investigator_id="inv1", skill_type=Skill.INTELLECT, amount=amount,
    )


class TestEmpowerSelf:
    def test_boost_adds_2_intellect_once(self, setup):
        """消耗：本次检定+2智力；随后检定不再享受。"""
        state, bus, inv, inst, impl = setup
        assert impl.boost(state, "inv1") is True
        assert inst.exhausted is True
        ctx = _intellect_ctx(state)
        bus.emit(ctx)
        assert ctx.amount == 5
        # 同一武装只生效一次
        ctx2 = _intellect_ctx(state)
        bus.emit(ctx2)
        assert ctx2.amount == 3

    def test_boost_only_intellect(self, setup):
        state, bus, inv, inst, impl = setup
        impl.boost(state, "inv1")
        ctx = EventContext(
            game_state=state, event=GameEvent.SKILL_VALUE_DETERMINED,
            investigator_id="inv1", skill_type=Skill.COMBAT, amount=3,
        )
        bus.emit(ctx)
        assert ctx.amount == 3

    def test_exhausted_blocks_boost(self, setup):
        state, bus, inv, inst, impl = setup
        inst.exhausted = True
        assert impl.boost(state, "inv1") is False

    def test_ignore_substitution_marker(self, setup):
        """在场时登记"可忽略意志代替智力"标记，离场移除。"""
        state, bus, inv, inst, impl = setup
        bus.emit(EventContext(
            game_state=state, event=GameEvent.CARD_ENTERS_PLAY,
            investigator_id="inv1", target="inst_emp",
            extra={"card_id": "empower_self_lv2"},
        ))
        assert "inv1" in state.scenario.vars["empower_self_ignore_sub"]
        bus.emit(EventContext(
            game_state=state, event=GameEvent.CARD_LEAVES_PLAY,
            investigator_id="inv1", target="inst_emp",
            extra={"card_id": "empower_self_lv2"},
        ))
        assert "inv1" not in state.scenario.vars["empower_self_ignore_sub"]
