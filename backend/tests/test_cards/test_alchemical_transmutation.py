"""Tests for Alchemical Transmutation (Level 0). (03032)

横置+1充能：意志检定(1)，每超过难度1点获得1资源（至多3）；
检定中揭示坏标记则受到1点伤害。
"""

import pytest
from backend.cards.mystic.alchemical_transmutation_lv0 import AlchemicalTransmutation
from backend.engine.event_bus import EventBus, EventContext
from backend.models.chaos import ChaosBag
from backend.models.enums import ChaosTokenType, GameEvent, Skill
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, ScenarioState,
)
from backend.tests.conftest import make_asset_data, make_investigator_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()

    inv_data = make_investigator_data(willpower=5)
    state.card_database[inv_data.id] = inv_data
    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1",
        resources=0,
    )
    state.investigators["inv1"] = inv

    state.card_database["alchemical_transmutation_lv0"] = make_asset_data(
        id="alchemical_transmutation_lv0", name="Alchemical Transmutation",
        traits=["spell"], uses={"charges": 3},
    )
    inst = CardInstance(
        instance_id="inst_alch", card_id="alchemical_transmutation_lv0",
        owner_id="inv1", controller_id="inv1",
    )
    inst.uses = {"charges": 3}
    state.cards_in_play["inst_alch"] = inst
    inv.play_area.append("inst_alch")

    impl = AlchemicalTransmutation("inst_alch")
    impl.register(bus, "inst_alch")
    return state, bus, inv, inst, impl


def _success_ctx(state, modified, difficulty):
    return EventContext(
        game_state=state, event=GameEvent.SKILL_TEST_SUCCESSFUL,
        investigator_id="inv1", skill_type=Skill.WILLPOWER,
        success=True, modified_skill=modified, difficulty=difficulty,
    )


class TestAlchemicalTransmutation:
    def test_activate_spends_charge_and_exhausts(self, setup):
        state, bus, inv, inst, impl = setup
        assert impl.activate(state, "inv1") is True
        assert inst.uses["charges"] == 2
        assert inst.exhausted is True

    def test_activate_fails_when_exhausted_or_empty(self, setup):
        state, bus, inv, inst, impl = setup
        inst.exhausted = True
        assert impl.activate(state, "inv1") is False
        inst.exhausted = False
        inst.uses["charges"] = 0
        assert impl.activate(state, "inv1") is False

    def test_success_gains_resources_per_margin_capped_at_3(self, setup):
        """成功：超难度2点→+2资源；超5点→封顶+3。"""
        state, bus, inv, inst, impl = setup
        impl.activate(state, "inv1")
        ctx = _success_ctx(state, modified=3, difficulty=1)
        bus.emit(ctx)
        assert inv.resources == 2
        assert ctx.extra["alchemical_transmutation_resources"] == 2

        # 第二次（重新就绪+充能后）：超5点封顶3
        inst.exhausted = False
        impl.activate(state, "inv1")
        ctx2 = _success_ctx(state, modified=6, difficulty=1)
        bus.emit(ctx2)
        assert inv.resources == 2 + 3

    def test_bad_token_deals_1_damage(self, setup):
        state, bus, inv, inst, impl = setup
        impl.activate(state, "inv1")
        ctx = EventContext(
            game_state=state, event=GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="inv1", skill_type=Skill.WILLPOWER,
            chaos_token=ChaosTokenType.CULTIST,
        )
        bus.emit(ctx)
        assert inv.damage == 1
        assert ctx.extra["alchemical_transmutation_damage"] is True

    def test_no_effect_when_not_armed(self, setup):
        """未启动时：检定成功不给资源，坏标记不造成伤害。"""
        state, bus, inv, inst, impl = setup
        ctx = _success_ctx(state, modified=6, difficulty=1)
        bus.emit(ctx)
        assert inv.resources == 0

        bus.emit(EventContext(
            game_state=state, event=GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="inv1", skill_type=Skill.WILLPOWER,
            chaos_token=ChaosTokenType.SKULL,
        ))
        assert inv.damage == 0

    def test_armed_state_cleared_after_test(self, setup):
        """一次检定结算后武装清除，下一次成功不再给资源。"""
        state, bus, inv, inst, impl = setup
        impl.activate(state, "inv1")
        bus.emit(_success_ctx(state, modified=3, difficulty=1))
        bus.emit(EventContext(
            game_state=state, event=GameEvent.SKILL_TEST_ENDS,
            investigator_id="inv1", success=True,
        ))
        bus.emit(_success_ctx(state, modified=3, difficulty=1))
        assert inv.resources == 2  # 只有第一次给
