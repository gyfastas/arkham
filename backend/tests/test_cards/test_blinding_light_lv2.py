"""Tests for Blinding Light (Level 2). (01069)

同0级，但成功造成2伤害；坏标记 → 失去1行动并受到1恐惧。
"""

import pytest
from backend.cards.mystic.blinding_light_lv2 import BlindingLightLv2
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import ChaosTokenType, GameEvent, Skill
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, ScenarioState,
)
from backend.tests.conftest import (
    make_enemy_data, make_event_data, make_investigator_data,
)


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()

    inv_data = make_investigator_data(willpower=4, agility=2)
    state.card_database[inv_data.id] = inv_data
    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1",
    )
    state.investigators["inv1"] = inv

    state.card_database["blinding_light_lv2"] = make_event_data(
        id="blinding_light_lv2", name="Blinding Light",
    )
    state.card_database["test_enemy"] = make_enemy_data()
    enemy = CardInstance(
        instance_id="enemy_1", card_id="test_enemy",
        owner_id="scenario", controller_id="scenario",
    )
    state.cards_in_play["enemy_1"] = enemy

    impl = BlindingLightLv2("inst_bl2")
    impl.register(bus, "inst_bl2")
    return state, bus, inv, enemy, impl


class TestBlindingLightLv2:
    def test_deals_2_damage_on_evade(self, setup):
        state, bus, inv, enemy, impl = setup
        bus.emit(EventContext(
            game_state=state, event=GameEvent.CARD_PLAYED,
            investigator_id="inv1", extra={"card_id": "blinding_light_lv2"},
        ))
        ctx = EventContext(
            game_state=state, event=GameEvent.ENEMY_EVADED,
            investigator_id="inv1", enemy_id="enemy_1",
        )
        bus.emit(ctx)
        assert enemy.damage == 2

    def test_bad_token_loses_action_and_takes_horror(self, setup):
        """坏标记：失去1行动并受到1恐惧。"""
        state, bus, inv, enemy, impl = setup
        inv.actions_remaining = 3
        bus.emit(EventContext(
            game_state=state, event=GameEvent.CARD_PLAYED,
            investigator_id="inv1", extra={"card_id": "blinding_light_lv2"},
        ))
        bus.emit(EventContext(
            game_state=state, event=GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="inv1", chaos_token=ChaosTokenType.AUTO_FAIL,
        ))
        bus.emit(EventContext(
            game_state=state, event=GameEvent.SKILL_TEST_ENDS,
            investigator_id="inv1",
        ))
        assert inv.actions_remaining == 2
        assert inv.horror == 1

    def test_willpower_substitute_no_bonus(self, setup):
        state, bus, inv, enemy, impl = setup
        bus.emit(EventContext(
            game_state=state, event=GameEvent.CARD_PLAYED,
            investigator_id="inv1", extra={"card_id": "blinding_light_lv2"},
        ))
        ctx = EventContext(
            game_state=state, event=GameEvent.SKILL_VALUE_DETERMINED,
            investigator_id="inv1", skill_type=Skill.AGILITY, amount=2,
        )
        bus.emit(ctx)
        assert ctx.amount == 4
