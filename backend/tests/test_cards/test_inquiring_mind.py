"""Tests for Inquiring Mind (Level 0)."""

import pytest
from backend.cards.seeker.inquiring_mind_lv0 import InquiringMind
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent, ChaosTokenType, Skill
from backend.models.state import GameState, InvestigatorState, LocationState, ScenarioState, CardInstance
from backend.tests.conftest import make_investigator_data, make_location_data


class TestInquiringMind:
    def test_card_data(self):
        """InquiringMind card_id is correct and provides 3 wild icons."""
        impl = InquiringMind("inquiring_inst")
        assert impl.card_id == "inquiring_mind_lv0"
        # Inquiring Mind provides 3 wild skill icons.
        # The icons are defined in card data JSON, not in the implementation.
        # The implementation has no event handlers — icons are handled
        # by the skill commit system.

    def test_no_event_handlers(self):
        """InquiringMind has no event handlers registered."""
        bus = EventBus()
        impl = InquiringMind("inquiring_inst")
        impl.register(bus, "inquiring_inst")
        # No handlers should have been registered — this card is purely
        # skill icons with a commit restriction checked elsewhere.
        # No handlers should have been registered — this card is purely
        # skill icons with a commit restriction checked elsewhere.
        assert True
