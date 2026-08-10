"""Tests for Forbidden Knowledge (Level 0). (01058)

使用(4秘密)。【快速】横置+受1恐惧：1秘密换1资源。无秘密时弃置。
"""

import pytest
from backend.cards.mystic.forbidden_knowledge_lv0 import ForbiddenKnowledge
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent
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
        resources=0,
    )
    state.investigators["inv1"] = inv

    state.card_database["forbidden_knowledge_lv0"] = make_asset_data(
        id="forbidden_knowledge_lv0", name="Forbidden Knowledge",
        traits=["talent"], uses={"secrets": 4},
    )
    inst = CardInstance(
        instance_id="inst_fk", card_id="forbidden_knowledge_lv0",
        owner_id="inv1", controller_id="inv1",
    )
    inst.uses = {"secrets": 4}
    state.cards_in_play["inst_fk"] = inst
    inv.play_area.append("inst_fk")

    impl = ForbiddenKnowledge("inst_fk")
    impl.register(bus, "inst_fk")
    return state, bus, inv, inst, impl


class TestForbiddenKnowledge:
    def test_enter_play_grants_4_secrets_if_missing(self, setup):
        state, bus, inv, inst, impl = setup
        inst.uses = {}
        bus.emit(EventContext(
            game_state=state, event=GameEvent.CARD_ENTERS_PLAY,
            investigator_id="inv1", target="inst_fk",
        ))
        assert inst.uses["secrets"] == 4

    def test_activate_gives_1_resource_costs_horror_and_exhaust(self, setup):
        """1秘密换1资源（旧实现的2资源为错误数值）；横置并受1恐惧。"""
        state, bus, inv, inst, impl = setup
        assert impl.activate(state, "inv1") is True
        assert inv.resources == 1
        assert inv.horror == 1
        assert inst.uses["secrets"] == 3
        assert inst.exhausted is True

    def test_cannot_activate_while_exhausted(self, setup):
        state, bus, inv, inst, impl = setup
        inst.exhausted = True
        assert impl.activate(state, "inv1") is False
        assert inv.resources == 0

    def test_discards_when_secrets_run_out(self, setup):
        """无秘密时弃置。"""
        state, bus, inv, inst, impl = setup
        inst.uses["secrets"] = 1
        assert impl.activate(state, "inv1") is True
        assert "inst_fk" not in inv.play_area
        assert "inst_fk" not in state.cards_in_play
        assert "forbidden_knowledge_lv0" in inv.discard
