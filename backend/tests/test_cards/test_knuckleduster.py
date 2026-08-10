"""Tests for Knuckleduster (Level 0)."""

import pytest
from backend.cards.rogue.knuckleduster_lv0 import Knuckleduster
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent, Skill
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, LocationState, ScenarioState,
)
from backend.tests.conftest import (
    make_enemy_data, make_investigator_data, make_location_data,
)


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()

    inv_data = make_investigator_data(health=7, sanity=7)
    state.card_database[inv_data.id] = inv_data
    state.card_database["ghoul"] = make_enemy_data(
        id="ghoul", fight=3, damage=2, horror=1,
    )
    state.card_database["retaliate_ghoul"] = make_enemy_data(
        id="retaliate_ghoul", fight=3, damage=2, horror=1,
        keywords=["retaliate"],
    )

    loc_data = make_location_data(id="loc1")
    state.card_database["loc1"] = loc_data
    state.locations["loc1"] = LocationState(
        location_id="loc1", card_data=loc_data, revealed=True,
    )

    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1",
    )
    state.investigators["inv1"] = inv

    state.cards_in_play["enemy_1"] = CardInstance(
        instance_id="enemy_1", card_id="ghoul",
        owner_id="scenario", controller_id="scenario",
    )
    inv.threat_area.append("enemy_1")

    weapon = CardInstance(
        instance_id="kd_inst", card_id="knuckleduster_lv0",
        owner_id="inv1", controller_id="inv1",
    )
    state.cards_in_play["kd_inst"] = weapon
    inv.play_area.append("kd_inst")

    impl = Knuckleduster("kd_inst")
    impl.register(bus, "kd_inst")
    return state, bus, inv, impl


def _fight(bus, state, enemy_id="enemy_1"):
    bus.emit(EventContext(
        game_state=state, event=GameEvent.FIGHT_ACTION_INITIATED,
        investigator_id="inv1", enemy_id=enemy_id, source="kd_inst",
    ))


def _test_result(bus, state, success, modified_skill=4, difficulty=3):
    event = GameEvent.SKILL_TEST_SUCCESSFUL if success else GameEvent.SKILL_TEST_FAILED
    ctx = EventContext(
        game_state=state, event=event,
        investigator_id="inv1", skill_type=Skill.COMBAT, success=success,
        modified_skill=modified_skill, difficulty=difficulty,
        source="kd_inst",
    )
    bus.emit(ctx)
    return ctx


class TestKnuckleduster:
    def test_card_id(self):
        assert Knuckleduster.card_id == "knuckleduster_lv0"

    def test_bonus_damage_on_success(self, setup):
        """This attack deals +1 damage."""
        state, bus, inv, impl = setup
        _fight(bus, state)
        ctx = _test_result(bus, state, success=True)
        assert ctx.extra["bonus_damage"] == 1

    def test_retaliate_on_failure(self, setup):
        """On a failed attack, the attacked enemy gains retaliate."""
        state, bus, inv, impl = setup
        _fight(bus, state)
        ctx = _test_result(bus, state, success=False)

        assert inv.damage == 2
        assert inv.horror == 1
        assert ctx.extra["knuckleduster_retaliate"] == "enemy_1"

    def test_no_retaliate_on_success(self, setup):
        state, bus, inv, impl = setup
        _fight(bus, state)
        _test_result(bus, state, success=True)
        assert inv.damage == 0
        assert inv.horror == 0

    def test_no_double_retaliate_with_keyword(self, setup):
        """Enemy that already has retaliate is not double-charged by the card."""
        state, bus, inv, impl = setup
        state.cards_in_play["enemy_2"] = CardInstance(
            instance_id="enemy_2", card_id="retaliate_ghoul",
            owner_id="scenario", controller_id="scenario",
        )
        inv.threat_area.append("enemy_2")
        _fight(bus, state, enemy_id="enemy_2")
        ctx = _test_result(bus, state, success=False)
        # Card's own retaliate grant is skipped (engine handles the keyword)
        assert inv.damage == 0
        assert "knuckleduster_retaliate" not in ctx.extra

    def test_other_weapon_source_ignored(self, setup):
        state, bus, inv, impl = setup
        ctx = EventContext(
            game_state=state, event=GameEvent.SKILL_TEST_SUCCESSFUL,
            investigator_id="inv1", skill_type=Skill.COMBAT, success=True,
            modified_skill=4, difficulty=3, source="other_weapon",
        )
        bus.emit(ctx)
        assert "bonus_damage" not in ctx.extra
