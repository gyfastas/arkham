"""Tests for Arcane Studies (Level 0). (01062)

【快速】花1资源：本次检定+1意志或+1智力。可重复支付叠加（引擎修复后验证）。
"""

import pytest
from backend.cards.mystic.arcane_studies_lv0 import ArcaneStudies
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

    inv_data = make_investigator_data()
    state.card_database[inv_data.id] = inv_data
    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1",
        resources=5,
    )
    state.investigators["inv1"] = inv

    state.card_database["arcane_studies_lv0"] = make_asset_data(
        id="arcane_studies_lv0", name="Arcane Studies", traits=["talent"],
    )
    inst = CardInstance(
        instance_id="inst_as", card_id="arcane_studies_lv0",
        owner_id="inv1", controller_id="inv1",
    )
    state.cards_in_play["inst_as"] = inst
    inv.play_area.append("inst_as")

    impl = ArcaneStudies("inst_as")
    impl.register(bus, "inst_as")
    return state, bus, inv, inst, impl


class TestArcaneStudies:
    def test_single_payment_boosts_one(self, setup):
        state, bus, inv, inst, impl = setup
        assert impl.spend(state, "inv1", Skill.WILLPOWER) is True
        assert inv.resources == 4
        ctx = EventContext(
            game_state=state, event=GameEvent.SKILL_VALUE_DETERMINED,
            investigator_id="inv1", skill_type=Skill.WILLPOWER, amount=3,
        )
        bus.emit(ctx)
        assert ctx.amount == 4

    def test_repeated_payments_stack(self, setup):
        """多次支付叠加：3资源换+3智力。"""
        state, bus, inv, inst, impl = setup
        for _ in range(3):
            assert impl.spend(state, "inv1", Skill.INTELLECT) is True
        assert inv.resources == 2
        ctx = EventContext(
            game_state=state, event=GameEvent.SKILL_VALUE_DETERMINED,
            investigator_id="inv1", skill_type=Skill.INTELLECT, amount=3,
        )
        bus.emit(ctx)
        assert ctx.amount == 6

    def test_boost_consumed_after_matching_test(self, setup):
        state, bus, inv, inst, impl = setup
        impl.spend(state, "inv1", Skill.WILLPOWER)
        bus.emit(EventContext(
            game_state=state, event=GameEvent.SKILL_VALUE_DETERMINED,
            investigator_id="inv1", skill_type=Skill.WILLPOWER, amount=3,
        ))
        ctx = EventContext(
            game_state=state, event=GameEvent.SKILL_VALUE_DETERMINED,
            investigator_id="inv1", skill_type=Skill.WILLPOWER, amount=3,
        )
        bus.emit(ctx)
        assert ctx.amount == 3

    def test_rejects_unsupported_skill(self, setup):
        state, bus, inv, inst, impl = setup
        assert impl.spend(state, "inv1", Skill.COMBAT) is False
        assert inv.resources == 5
