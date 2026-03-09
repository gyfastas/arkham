"""Tests for Guts (Level 0)."""

import pytest
from backend.cards.neutral.guts_lv0 import Guts
from backend.engine.event_bus import EventBus
from backend.engine.skill_test import SkillTestEngine
from backend.models.chaos import ChaosBag
from backend.models.enums import ChaosTokenType, Skill
from backend.models.state import GameState, InvestigatorState, ScenarioState
from backend.tests.conftest import make_investigator_data, make_skill_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()
    bag = ChaosBag()
    bag.seed(42)

    inv_data = make_investigator_data(willpower=3)
    state.card_database[inv_data.id] = inv_data

    guts_data = make_skill_data(id="guts_lv0", skill_icons={"willpower": 2})
    state.card_database["guts_lv0"] = guts_data

    inv = InvestigatorState(
        investigator_id="inv1",
        card_data=inv_data,
        location_id="loc1",
        deck=["card_a", "card_b", "card_c"],
    )
    inv.hand.append("guts_lv0")
    state.investigators["inv1"] = inv

    engine = SkillTestEngine(state, bus, bag)

    # Register Guts implementation
    guts_impl = Guts("guts_impl")
    guts_impl.register(bus, "guts_impl")

    return state, bus, bag, engine, inv


class TestGuts:
    def test_provides_willpower_icons(self, setup):
        state, bus, bag, engine, inv = setup
        bag.tokens = [ChaosTokenType.ZERO]

        result = engine.run_test(
            investigator_id="inv1",
            skill_type=Skill.WILLPOWER,
            difficulty=5,
            committed_card_ids=["guts_lv0"],
        )
        # base 3 + 2 icons + 0 = 5 >= 5
        assert result.success
        assert result.committed_icons == 2

    def test_draw_card_on_success(self, setup):
        state, bus, bag, engine, inv = setup
        bag.tokens = [ChaosTokenType.ZERO]
        initial_hand = len(inv.hand)
        initial_deck = len(inv.deck)

        result = engine.run_test(
            investigator_id="inv1",
            skill_type=Skill.WILLPOWER,
            difficulty=3,
            committed_card_ids=["guts_lv0"],
        )
        assert result.success
        # guts_lv0 discarded from hand, but drew 1 card from deck
        # Net: hand should have initial - 1 (committed) + 1 (drawn)
        # But committed cards are removed in ST.8, and draw happens in ST.6
        # So: hand = initial_hand - 1 (committed to discard) + 1 (drawn) = initial_hand
        assert len(inv.deck) == initial_deck - 1

    def test_no_draw_on_failure(self, setup):
        state, bus, bag, engine, inv = setup
        bag.tokens = [ChaosTokenType.AUTO_FAIL]
        initial_deck = len(inv.deck)

        engine.run_test(
            investigator_id="inv1",
            skill_type=Skill.WILLPOWER,
            difficulty=3,
            committed_card_ids=["guts_lv0"],
        )
        # Should not draw on failure
        assert len(inv.deck) == initial_deck
