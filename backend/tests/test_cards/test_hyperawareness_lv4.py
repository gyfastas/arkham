"""Tests for Hyperawareness (Level 4)."""

import pytest
from backend.cards.seeker.hyperawareness_lv4 import HyperawarenessLv4
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent, Skill
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, LocationState, ScenarioState,
)
from backend.tests.conftest import make_investigator_data, make_location_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()

    inv_data = make_investigator_data(intellect=3, agility=3)
    state.card_database[inv_data.id] = inv_data
    loc_data = make_location_data()
    state.card_database[loc_data.id] = loc_data

    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data,
        location_id="test_location", resources=1,
    )
    state.investigators["inv1"] = inv
    state.locations["test_location"] = LocationState(
        location_id="test_location", card_data=loc_data,
    )

    inst = CardInstance(
        instance_id="hyp_1", card_id="hyperawareness_lv4",
        owner_id="inv1", controller_id="inv1",
    )
    inst.uses = {"resourcess": 2}  # 生产数据的双 s 键
    state.cards_in_play["hyp_1"] = inst
    inv.play_area.append("hyp_1")

    impl = HyperawarenessLv4("hyp_1")
    impl.register(bus, "hyp_1")
    return state, bus, inv, inst, impl


def _skill_ctx(state, bus, skill, base):
    ctx = EventContext(
        game_state=state, event=GameEvent.SKILL_VALUE_DETERMINED,
        investigator_id="inv1", skill_type=skill, amount=base,
    )
    bus.emit(ctx)
    return ctx


def _test_ends(state, bus):
    bus.emit(EventContext(
        game_state=state, event=GameEvent.SKILL_TEST_ENDS, investigator_id="inv1",
    ))


class TestHyperawarenessLv4:
    def test_spend_from_card_resources(self, setup):
        """默认优先扣本卡上的资源标记：本次检定+1智力。"""
        state, bus, inv, inst, impl = setup
        assert impl.spend(state, "inv1", Skill.INTELLECT) is True
        assert inst.uses["resourcess"] == 1
        assert inv.resources == 1  # 资源池未动

        ctx = _skill_ctx(state, bus, Skill.INTELLECT, 3)
        assert ctx.amount == 4
        _test_ends(state, bus)

    def test_spend_falls_back_to_pool(self, setup):
        """本卡资源耗尽后回落到资源池。"""
        state, bus, inv, inst, impl = setup
        impl.spend(state, "inv1", Skill.AGILITY)
        impl.spend(state, "inv1", Skill.AGILITY)
        assert inst.uses["resourcess"] == 0
        # 第三次从资源池扣
        assert impl.spend(state, "inv1", Skill.AGILITY) is True
        assert inv.resources == 0
        # 资源池也空了：不能再支付
        assert impl.spend(state, "inv1", Skill.AGILITY) is False

        ctx = _skill_ctx(state, bus, Skill.AGILITY, 3)
        assert ctx.amount == 6  # 3次叠加
        _test_ends(state, bus)

    def test_replenish_at_round_begins(self, setup):
        """每轮开始：本卡资源补满至2。"""
        state, bus, inv, inst, impl = setup
        impl.spend(state, "inv1", Skill.INTELLECT)
        impl.spend(state, "inv1", Skill.INTELLECT)
        assert inst.uses["resourcess"] == 0
        _test_ends(state, bus)

        bus.emit(EventContext(game_state=state, event=GameEvent.ROUND_BEGINS))
        assert inst.uses["resourcess"] == 2

    def test_only_boosted_skills(self, setup):
        """只能提升智力/敏捷。"""
        state, bus, inv, inst, impl = setup
        assert impl.spend(state, "inv1", Skill.COMBAT) is False
        assert inst.uses["resourcess"] == 2
