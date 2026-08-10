"""Tests for Ethereal Form (Level 0). (06164)

躲避：意志值加入技能值；成功则解除其余交战，本轮视为无形
（无形期间你的战斗行动被取消；回合结束清除）。
"""

import pytest
from backend.cards.mystic.ethereal_form_lv0 import EtherealForm
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent, Skill
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, LocationState, ScenarioState,
)
from backend.tests.conftest import (
    make_enemy_data, make_event_data, make_investigator_data, make_location_data,
)


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()
    inv_data = make_investigator_data(willpower=5, agility=3)
    state.card_database[inv_data.id] = inv_data
    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1",
    )
    state.investigators["inv1"] = inv
    loc_data = make_location_data(id="loc1")
    state.card_database["loc1"] = loc_data
    state.locations["loc1"] = LocationState(location_id="loc1", card_data=loc_data)

    state.card_database["ethereal_form_lv0"] = make_event_data(
        id="ethereal_form_lv0", name="Ethereal Form", cost=2)
    state.card_database["test_enemy"] = make_enemy_data()
    for eid in ("enemy_1", "enemy_2"):
        state.cards_in_play[eid] = CardInstance(
            instance_id=eid, card_id="test_enemy",
            owner_id="scenario", controller_id="scenario",
        )
        inv.threat_area.append(eid)

    impl = EtherealForm("impl_ef")
    impl.register(bus, "impl_ef")
    return state, bus, inv, impl


def _play_and_evade(state, bus):
    bus.emit(EventContext(
        game_state=state, event=GameEvent.CARD_PLAYED,
        investigator_id="inv1", extra={"card_id": "ethereal_form_lv0"},
    ))
    ctx = EventContext(
        game_state=state, event=GameEvent.SKILL_VALUE_DETERMINED,
        investigator_id="inv1", skill_type=Skill.AGILITY, amount=3,
    )
    bus.emit(ctx)
    return ctx


class TestEtherealForm:
    def test_adds_willpower_to_agility(self, setup):
        """躲避检定：敏捷(3)+意志(5)=8。"""
        state, bus, inv, impl = setup
        ctx = _play_and_evade(state, bus)
        assert ctx.amount == 8

    def test_success_disengages_others_and_ethereal(self, setup):
        """成功：其余交战敌人解除交战并放回地点；本轮视为无形。"""
        state, bus, inv, impl = setup
        _play_and_evade(state, bus)
        # 引擎躲避成功会先移除 enemy_1；模拟
        inv.threat_area.remove("enemy_1")
        ctx = EventContext(
            game_state=state, event=GameEvent.ENEMY_EVADED,
            investigator_id="inv1", enemy_id="enemy_1",
        )
        bus.emit(ctx)
        assert inv.threat_area == []
        assert "enemy_2" in state.locations["loc1"].enemies
        assert ctx.extra["ethereal_form_disengaged"] == ["enemy_2"]
        assert inv.active_effects["ethereal_form_ethereal"] is True

    def test_ethereal_cancels_fight(self, setup):
        """无形期间：你的战斗行动被取消。"""
        state, bus, inv, impl = setup
        inv.active_effects = {"ethereal_form_ethereal": True}
        ctx = EventContext(
            game_state=state, event=GameEvent.FIGHT_ACTION_INITIATED,
            investigator_id="inv1", enemy_id="enemy_2",
        )
        bus.emit(ctx)
        assert ctx.cancelled is True

    def test_ethereal_cleared_at_round_end(self, setup):
        state, bus, inv, impl = setup
        inv.active_effects = {"ethereal_form_ethereal": True}
        bus.emit(EventContext(
            game_state=state, event=GameEvent.ROUND_ENDS,
        ))
        assert "ethereal_form_ethereal" not in inv.active_effects
