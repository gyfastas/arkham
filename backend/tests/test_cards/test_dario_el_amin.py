"""Tests for Dario El-Amin (Level 0)."""

import pytest
from backend.cards.rogue.dario_el_amin_lv0 import DarioElAmin
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent, Skill
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, LocationState, ScenarioState,
)
from backend.tests.conftest import (
    make_asset_data, make_enemy_data, make_investigator_data,
    make_location_data,
)


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()

    inv_data = make_investigator_data(willpower=3, intellect=3, combat=3)
    state.card_database[inv_data.id] = inv_data
    state.card_database["dario_el_amin_lv0"] = make_asset_data(
        id="dario_el_amin_lv0", cost=4, health=2, sanity=2,
    )
    state.card_database["ghoul"] = make_enemy_data(id="ghoul")

    loc_data = make_location_data(id="loc1")
    state.card_database["loc1"] = loc_data
    state.locations["loc1"] = LocationState(
        location_id="loc1", card_data=loc_data, revealed=True,
    )

    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1",
        resources=10,
    )
    state.investigators["inv1"] = inv

    ci = CardInstance(
        instance_id="dario_inst", card_id="dario_el_amin_lv0",
        owner_id="inv1", controller_id="inv1",
    )
    state.cards_in_play["dario_inst"] = ci
    inv.play_area.append("dario_inst")

    impl = DarioElAmin("dario_inst")
    impl.register(bus, "dario_inst")
    return state, bus, inv, impl, ci


def _value_ctx(state, skill, amount=3):
    return EventContext(
        game_state=state, event=GameEvent.SKILL_VALUE_DETERMINED,
        investigator_id="inv1", skill_type=skill, amount=amount,
    )


class TestDarioElAmin:
    def test_card_id(self):
        assert DarioElAmin.card_id == "dario_el_amin_lv0"

    def test_bonus_at_10_resources(self, setup):
        """10+ resources: +1 willpower and +1 intellect."""
        state, bus, inv, impl, ci = setup
        for skill in (Skill.WILLPOWER, Skill.INTELLECT):
            ctx = _value_ctx(state, skill)
            bus.emit(ctx)
            assert ctx.amount == 4

    def test_no_bonus_for_other_skills(self, setup):
        state, bus, inv, impl, ci = setup
        ctx = _value_ctx(state, Skill.COMBAT)
        bus.emit(ctx)
        assert ctx.amount == 3

    def test_no_bonus_below_10_resources(self, setup):
        state, bus, inv, impl, ci = setup
        inv.resources = 9
        ctx = _value_ctx(state, Skill.WILLPOWER)
        bus.emit(ctx)
        assert ctx.amount == 3

    def test_activate_gains_2_resources(self, setup):
        """Action, no enemies at your location: exhaust, gain 2 resources."""
        state, bus, inv, impl, ci = setup
        assert impl.activate(state, "inv1") is True
        assert ci.exhausted is True
        assert inv.resources == 12

    def test_activate_blocked_by_location_enemy(self, setup):
        state, bus, inv, impl, ci = setup
        state.cards_in_play["enemy_1"] = CardInstance(
            instance_id="enemy_1", card_id="ghoul",
            owner_id="scenario", controller_id="scenario",
        )
        state.locations["loc1"].enemies.append("enemy_1")
        assert impl.activate(state, "inv1") is False
        assert ci.exhausted is False

    def test_activate_blocked_by_engaged_enemy(self, setup):
        state, bus, inv, impl, ci = setup
        state.cards_in_play["enemy_1"] = CardInstance(
            instance_id="enemy_1", card_id="ghoul",
            owner_id="scenario", controller_id="scenario",
        )
        inv.threat_area.append("enemy_1")
        assert impl.activate(state, "inv1") is False

    def test_activate_fails_when_exhausted(self, setup):
        state, bus, inv, impl, ci = setup
        ci.exhausted = True
        assert impl.activate(state, "inv1") is False
