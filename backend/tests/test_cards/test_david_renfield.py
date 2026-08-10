"""Tests for David Renfield (Level 0). (03112)

身上有毁灭标记时+1意志；【快速】横置：放置1毁灭，每有1毁灭获得1资源。
"""

import pytest
from backend.cards.mystic.david_renfield_lv0 import DavidRenfield
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

    inv_data = make_investigator_data(willpower=3)
    state.card_database[inv_data.id] = inv_data
    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1",
        resources=0,
    )
    state.investigators["inv1"] = inv

    state.card_database["david_renfield_lv0"] = make_asset_data(
        id="david_renfield_lv0", name="David Renfield", cost=2,
        traits=["ally", "patron"], health=2, sanity=1,
    )
    inst = CardInstance(
        instance_id="inst_dave", card_id="david_renfield_lv0",
        owner_id="inv1", controller_id="inv1",
    )
    state.cards_in_play["inst_dave"] = inst
    inv.play_area.append("inst_dave")

    impl = DavidRenfield("inst_dave")
    impl.register(bus, "inst_dave")
    return state, bus, inv, inst, impl


def _willpower_ctx(state, amount=3):
    return EventContext(
        game_state=state, event=GameEvent.SKILL_VALUE_DETERMINED,
        investigator_id="inv1", skill_type=Skill.WILLPOWER, amount=amount,
    )


class TestDavidRenfield:
    def test_no_bonus_without_doom(self, setup):
        state, bus, inv, inst, impl = setup
        ctx = _willpower_ctx(state)
        bus.emit(ctx)
        assert ctx.amount == 3

    def test_willpower_bonus_with_doom(self, setup):
        """至少1个毁灭标记：+1意志。"""
        state, bus, inv, inst, impl = setup
        inst.doom = 1
        ctx = _willpower_ctx(state)
        bus.emit(ctx)
        assert ctx.amount == 4

    def test_bonus_only_for_willpower(self, setup):
        state, bus, inv, inst, impl = setup
        inst.doom = 2
        ctx = EventContext(
            game_state=state, event=GameEvent.SKILL_VALUE_DETERMINED,
            investigator_id="inv1", skill_type=Skill.COMBAT, amount=3,
        )
        bus.emit(ctx)
        assert ctx.amount == 3

    def test_activate_places_doom_and_gains_resources(self, setup):
        """横置：放1毁灭，获得1资源（每毁灭1资源）。"""
        state, bus, inv, inst, impl = setup
        assert impl.activate(state, "inv1") is True
        assert inst.exhausted is True
        assert inst.doom == 1
        assert inv.resources == 1

    def test_activate_scales_with_doom(self, setup):
        """已有2毁灭时启动：放第3个毁灭，获得3资源。"""
        state, bus, inv, inst, impl = setup
        inst.doom = 2
        assert impl.activate(state, "inv1") is True
        assert inst.doom == 3
        assert inv.resources == 3

    def test_activate_without_placing_doom(self, setup):
        """可选分支：不放置毁灭，按现有毁灭数给资源。"""
        state, bus, inv, inst, impl = setup
        inst.doom = 2
        assert impl.activate(state, "inv1", place_doom=False) is True
        assert inst.doom == 2
        assert inv.resources == 2

    def test_activate_fails_while_exhausted(self, setup):
        state, bus, inv, inst, impl = setup
        inst.exhausted = True
        assert impl.activate(state, "inv1") is False
        assert inst.doom == 0
        assert inv.resources == 0

    def test_doom_counts_toward_total_doom(self, setup):
        """放置的毁灭计入全场毁灭总数（ agendas 推进口径）。"""
        state, bus, inv, inst, impl = setup
        impl.activate(state, "inv1")
        assert state.total_doom_in_play() == 1
