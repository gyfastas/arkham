"""Tests for Cat Burglar (Level 1)."""

import pytest
from backend.cards.rogue.cat_burglar_lv1 import CatBurglar
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent, Skill
from backend.models.state import GameState, InvestigatorState, ScenarioState, CardInstance
from backend.tests.conftest import make_investigator_data, make_asset_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()

    inv_data = make_investigator_data(agility=3)
    state.card_database[inv_data.id] = inv_data

    inv = InvestigatorState(
        investigator_id="inv1",
        card_data=inv_data,
        location_id="loc1",
    )
    state.investigators["inv1"] = inv

    impl = CatBurglar("catburg_inst")
    impl.register(bus, "catburg_inst")

    ci = CardInstance(instance_id="catburg_inst", card_id="cat_burglar_lv1", owner_id="inv1", controller_id="inv1")
    state.cards_in_play["catburg_inst"] = ci
    inv.play_area.append("catburg_inst")

    return state, bus, inv, impl


class TestCatBurglar:
    def test_agility_bonus(self, setup):
        """Cat Burglar provides +1 agility during skill value determination."""
        state, bus, inv, impl = setup

        ctx = EventContext(
            game_state=state,
            event=GameEvent.SKILL_VALUE_DETERMINED,
            investigator_id="inv1",
            extra={"skill_type": Skill.AGILITY, "skill_value": 3},
        )
        bus.emit(ctx)

        assert ctx.extra["skill_value"] == 4

    def test_no_bonus_for_other_skills(self, setup):
        """Cat Burglar does not boost non-agility skills."""
        state, bus, inv, impl = setup

        ctx = EventContext(
            game_state=state,
            event=GameEvent.SKILL_VALUE_DETERMINED,
            investigator_id="inv1",
            extra={"skill_type": Skill.COMBAT, "skill_value": 3},
        )
        bus.emit(ctx)

        assert ctx.extra["skill_value"] == 3
