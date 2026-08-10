"""Tests for Blood Pact (Level 0). (07158)

[fast]在本卡放1毁灭：本次检定+2意志或+2战斗（每个能力每次检定限一次）。
"""

import pytest
from backend.cards.mystic.blood_pact_lv0 import BloodPact
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
    inv_data = make_investigator_data(willpower=3, combat=3)
    state.card_database[inv_data.id] = inv_data
    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1",
    )
    state.investigators["inv1"] = inv
    state.card_database["blood_pact_lv0"] = make_asset_data(
        id="blood_pact_lv0", name="Blood Pact", traits=["spell", "pact"])
    inst = CardInstance(
        instance_id="inst_bp", card_id="blood_pact_lv0",
        owner_id="inv1", controller_id="inv1",
    )
    state.cards_in_play["inst_bp"] = inst
    inv.play_area.append("inst_bp")
    impl = BloodPact("inst_bp")
    impl.register(bus, "inst_bp")
    return state, bus, inv, inst, impl


def _skill_ctx(state, skill, amount):
    return EventContext(
        game_state=state, event=GameEvent.SKILL_VALUE_DETERMINED,
        investigator_id="inv1", skill_type=skill, amount=amount,
    )


class TestBloodPact:
    def test_boost_willpower_adds_doom_and_bonus(self, setup):
        """放1毁灭：本次检定意志+2。"""
        state, bus, inv, inst, impl = setup
        assert impl.boost(state, "inv1", Skill.WILLPOWER) is True
        assert inst.doom == 1
        ctx = _skill_ctx(state, Skill.WILLPOWER, 3)
        bus.emit(ctx)
        assert ctx.amount == 5

    def test_boost_combat(self, setup):
        state, bus, inv, inst, impl = setup
        assert impl.boost_combat(state, "inv1") is True
        ctx = _skill_ctx(state, Skill.COMBAT, 3)
        bus.emit(ctx)
        assert ctx.amount == 5

    def test_limit_once_per_test_per_ability(self, setup):
        """同一能力每次检定限一次；另一能力仍可用。"""
        state, bus, inv, inst, impl = setup
        assert impl.boost_willpower(state, "inv1") is True
        assert impl.boost_willpower(state, "inv1") is False
        assert impl.boost_combat(state, "inv1") is True
        assert inst.doom == 2

    def test_doom_counts_in_play(self, setup):
        """本卡上的毁灭计入场上总毁灭。"""
        state, bus, inv, inst, impl = setup
        impl.boost(state, "inv1", Skill.WILLPOWER)
        assert state.total_doom_in_play() == 1

    def test_reset_after_test(self, setup):
        state, bus, inv, inst, impl = setup
        impl.boost_willpower(state, "inv1")
        bus.emit(EventContext(
            game_state=state, event=GameEvent.SKILL_TEST_ENDS,
            investigator_id="inv1",
        ))
        assert impl.boost_willpower(state, "inv1") is True
