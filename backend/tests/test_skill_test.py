"""Tests for SkillTestEngine (ST.1 through ST.8)."""

import pytest
from backend.engine.event_bus import EventBus, EventContext
from backend.engine.skill_test import SkillTestEngine
from backend.models.chaos import ChaosBag
from backend.models.enums import ChaosTokenType, GameEvent, Skill, TimingPriority
from backend.models.state import GameState, ScenarioState
from backend.tests.conftest import make_investigator_data, make_skill_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()
    bag = ChaosBag()
    bag.seed(42)

    inv_data = make_investigator_data(combat=4, intellect=3)
    state.card_database[inv_data.id] = inv_data

    from backend.models.state import InvestigatorState
    inv = InvestigatorState(
        investigator_id="test_investigator",
        card_data=inv_data,
        location_id="loc1",
    )
    state.investigators["test_investigator"] = inv

    engine = SkillTestEngine(state, bus, bag)
    return state, bus, bag, engine, inv


class TestSkillTest:
    def test_basic_success(self, setup):
        state, bus, bag, engine, inv = setup
        # Force a +1 token for guaranteed success
        bag.tokens = [ChaosTokenType.PLUS_1]

        result = engine.run_test(
            investigator_id="test_investigator",
            skill_type=Skill.COMBAT,
            difficulty=3,
        )
        # base 4 + token +1 = 5 >= 3
        assert result.success
        assert result.base_skill == 4
        assert result.token == ChaosTokenType.PLUS_1

    def test_basic_failure(self, setup):
        state, bus, bag, engine, inv = setup
        bag.tokens = [ChaosTokenType.MINUS_4]

        result = engine.run_test(
            investigator_id="test_investigator",
            skill_type=Skill.COMBAT,
            difficulty=3,
        )
        # base 4 + (-4) = 0 < 3
        assert not result.success

    def test_auto_fail(self, setup):
        state, bus, bag, engine, inv = setup
        bag.tokens = [ChaosTokenType.AUTO_FAIL]

        result = engine.run_test(
            investigator_id="test_investigator",
            skill_type=Skill.COMBAT,
            difficulty=1,
        )
        assert not result.success
        assert result.auto_fail

    def test_committed_cards_add_icons(self, setup):
        state, bus, bag, engine, inv = setup
        bag.tokens = [ChaosTokenType.MINUS_2]

        skill_data = make_skill_data(skill_icons={"combat": 2})
        state.card_database["combat_skill"] = skill_data
        inv.hand.append("combat_skill")

        result = engine.run_test(
            investigator_id="test_investigator",
            skill_type=Skill.COMBAT,
            difficulty=4,
            committed_card_ids=["combat_skill"],
        )
        # base 4 + 2 icons + (-2) = 4 >= 4
        assert result.success
        assert result.committed_icons == 2

    def test_committed_cards_discarded_after_test(self, setup):
        state, bus, bag, engine, inv = setup
        bag.tokens = [ChaosTokenType.ZERO]

        skill_data = make_skill_data(id="guts", skill_icons={"willpower": 2})
        state.card_database["guts"] = skill_data
        inv.hand.append("guts")

        engine.run_test(
            investigator_id="test_investigator",
            skill_type=Skill.WILLPOWER,
            difficulty=3,
            committed_card_ids=["guts"],
        )
        assert "guts" not in inv.hand
        assert "guts" in inv.discard

    def test_wild_icons_count(self, setup):
        state, bus, bag, engine, inv = setup
        bag.tokens = [ChaosTokenType.ZERO]

        skill_data = make_skill_data(id="wild_skill", skill_icons={"wild": 3})
        state.card_database["wild_skill"] = skill_data
        inv.hand.append("wild_skill")

        result = engine.run_test(
            investigator_id="test_investigator",
            skill_type=Skill.INTELLECT,
            difficulty=6,
            committed_card_ids=["wild_skill"],
        )
        # base 3 + 3 wild + 0 = 6 >= 6
        assert result.success

    def test_on_success_callback(self, setup):
        state, bus, bag, engine, inv = setup
        bag.tokens = [ChaosTokenType.PLUS_1]
        callback_fired = []

        def on_success(result):
            callback_fired.append(True)

        engine.run_test(
            investigator_id="test_investigator",
            skill_type=Skill.COMBAT,
            difficulty=3,
            on_success=on_success,
        )
        assert callback_fired == [True]

    def test_on_failure_callback(self, setup):
        state, bus, bag, engine, inv = setup
        bag.tokens = [ChaosTokenType.MINUS_8]
        callback_fired = []

        def on_failure(result):
            callback_fired.append(True)

        engine.run_test(
            investigator_id="test_investigator",
            skill_type=Skill.COMBAT,
            difficulty=3,
            on_failure=on_failure,
        )
        assert callback_fired == [True]

    def test_event_bus_hooks_fire(self, setup):
        state, bus, bag, engine, inv = setup
        bag.tokens = [ChaosTokenType.ZERO]
        events_seen = []

        for evt in [GameEvent.SKILL_TEST_BEGINS, GameEvent.SKILL_TEST_COMMIT,
                     GameEvent.CHAOS_TOKEN_REVEALED, GameEvent.SKILL_TEST_ENDS]:
            bus.register(evt, lambda ctx, e=evt: events_seen.append(e))

        engine.run_test(
            investigator_id="test_investigator",
            skill_type=Skill.COMBAT,
            difficulty=3,
        )
        assert GameEvent.SKILL_TEST_BEGINS in events_seen
        assert GameEvent.CHAOS_TOKEN_REVEALED in events_seen
        assert GameEvent.SKILL_TEST_ENDS in events_seen

    def test_card_modifier_via_bus(self, setup):
        state, bus, bag, engine, inv = setup
        bag.tokens = [ChaosTokenType.ZERO]

        # A card ability that adds +2 to combat during skill value determination
        def boost_combat(ctx):
            if ctx.skill_type == Skill.COMBAT:
                ctx.modify_amount(2, "weapon_bonus")

        bus.register(GameEvent.SKILL_VALUE_DETERMINED, boost_combat, TimingPriority.WHEN)

        result = engine.run_test(
            investigator_id="test_investigator",
            skill_type=Skill.COMBAT,
            difficulty=6,
        )
        # base 4 + 0 token + 2 boost = 6 >= 6
        assert result.success
        assert result.modified_skill == 6

    def test_modified_skill_cannot_go_below_zero(self, setup):
        state, bus, bag, engine, inv = setup
        bag.tokens = [ChaosTokenType.MINUS_8]

        result = engine.run_test(
            investigator_id="test_investigator",
            skill_type=Skill.INTELLECT,
            difficulty=1,
        )
        # base 3 + (-8) = -5, clamped to 0
        assert result.modified_skill == 0
        assert not result.success
