"""Tests for Hyperawareness (Level 0)."""

import pytest
from backend.cards.seeker.hyperawareness_lv0 import Hyperawareness
from backend.engine.event_bus import EventBus
from backend.models.state import GameState, InvestigatorState, ScenarioState, CardInstance
from backend.tests.conftest import make_investigator_data, make_asset_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()

    inv_data = make_investigator_data()
    state.card_database[inv_data.id] = inv_data

    ha_data = make_asset_data(
        id="hyperawareness_lv0", name="Hyperawareness",
        skill_icons={"intellect": 1, "agility": 1},
    )
    state.card_database["hyperawareness_lv0"] = ha_data

    inv = InvestigatorState(
        investigator_id="inv1",
        card_data=inv_data,
        location_id="test_location",
        deck=[],
    )
    state.investigators["inv1"] = inv

    impl = Hyperawareness("inst_ha")
    impl.register(bus, "inst_ha")

    ci = CardInstance(instance_id="inst_ha", card_id="hyperawareness_lv0", owner_id="inv1", controller_id="inv1")
    state.cards_in_play["inst_ha"] = ci
    inv.play_area.append("inst_ha")

    return state, bus, inv, impl


class TestHyperawareness:
    def test_card_data_icons(self, setup):
        """Hyperawareness has intellect and agility skill icons."""
        state, bus, inv, impl = setup
        card_data = state.card_database["hyperawareness_lv0"]
        assert card_data.skill_icons.get("intellect") == 1
        assert card_data.skill_icons.get("agility") == 1

    def test_spend_boosts_intellect(self, setup):
        """花1资源：本次智力检定+1。"""
        from backend.models.enums import GameEvent, Skill
        from backend.engine.event_bus import EventContext
        state, bus, inv, impl = setup
        inv.resources = 2

        assert impl.spend(state, "inv1", Skill.INTELLECT) is True
        assert inv.resources == 1

        ctx = EventContext(
            game_state=state, event=GameEvent.SKILL_VALUE_DETERMINED,
            investigator_id="inv1", skill_type=Skill.INTELLECT, amount=3,
        )
        bus.emit(ctx)
        assert ctx.amount == 4

    def test_spend_stacks_multiple_times(self, setup):
        """官方：快速能力可多次支付叠加（2资源→+2敏捷）。"""
        from backend.models.enums import GameEvent, Skill
        from backend.engine.event_bus import EventContext
        state, bus, inv, impl = setup
        inv.resources = 2

        assert impl.spend(state, "inv1", Skill.AGILITY) is True
        assert impl.spend(state, "inv1", Skill.AGILITY) is True
        assert inv.resources == 0

        ctx = EventContext(
            game_state=state, event=GameEvent.SKILL_VALUE_DETERMINED,
            investigator_id="inv1", skill_type=Skill.AGILITY, amount=3,
        )
        bus.emit(ctx)
        assert ctx.amount == 5

    def test_spend_rejects_wrong_skill(self, setup):
        """只能提升智力/敏捷。"""
        from backend.models.enums import Skill
        state, bus, inv, impl = setup
        inv.resources = 5
        assert impl.spend(state, "inv1", Skill.COMBAT) is False
        assert impl.spend(state, "inv1", Skill.WILLPOWER) is False
        assert inv.resources == 5

    def test_spend_requires_resources(self, setup):
        from backend.models.enums import Skill
        state, bus, inv, impl = setup
        inv.resources = 0
        assert impl.spend(state, "inv1", Skill.INTELLECT) is False
