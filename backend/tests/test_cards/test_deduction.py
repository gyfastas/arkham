"""Tests for Deduction (Level 0)."""

import pytest
from backend.cards.seeker.deduction_lv0 import Deduction
from backend.engine.event_bus import EventBus
from backend.engine.skill_test import SkillTestEngine
from backend.models.chaos import ChaosBag
from backend.models.enums import Action, ChaosTokenType, Skill
from backend.models.state import GameState, InvestigatorState, LocationState, ScenarioState
from backend.tests.conftest import make_investigator_data, make_location_data, make_skill_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()
    bag = ChaosBag()
    bag.seed(42)

    inv_data = make_investigator_data(intellect=3)
    state.card_database[inv_data.id] = inv_data

    deduction_data = make_skill_data(id="deduction_lv0", skill_icons={"intellect": 1})
    state.card_database["deduction_lv0"] = deduction_data

    loc_data = make_location_data(shroud=2)
    state.card_database[loc_data.id] = loc_data

    inv = InvestigatorState(
        investigator_id="inv1",
        card_data=inv_data,
        location_id="test_location",
        deck=["card_a", "card_b"],
    )
    inv.hand.append("deduction_lv0")
    state.investigators["inv1"] = inv

    loc = LocationState(location_id="test_location", card_data=loc_data, clues=3)
    state.locations["test_location"] = loc

    engine = SkillTestEngine(state, bus, bag)

    deduction_impl = Deduction("deduction_impl")
    deduction_impl.register(bus, "deduction_impl")

    return state, bus, bag, engine, inv, loc


class TestDeduction:
    def test_provides_intellect_icon(self, setup):
        state, bus, bag, engine, inv, loc = setup
        bag.tokens = [ChaosTokenType.ZERO]

        result = engine.run_test(
            investigator_id="inv1",
            skill_type=Skill.INTELLECT,
            difficulty=4,
            committed_card_ids=["deduction_lv0"],
        )
        # base 3 + 1 icon + 0 = 4 >= 4
        assert result.success
        assert result.committed_icons == 1

    def test_extra_clue_on_success(self, setup):
        state, bus, bag, engine, inv, loc = setup
        bag.tokens = [ChaosTokenType.PLUS_1]
        initial_clues = inv.clues
        initial_loc_clues = loc.clues

        result = engine.run_test(
            investigator_id="inv1",
            skill_type=Skill.INTELLECT,
            difficulty=2,
            committed_card_ids=["deduction_lv0"],
        )
        assert result.success
        # Deduction grants 1 extra clue (on top of whatever the investigate action gives)
        assert inv.clues == initial_clues + 1
        assert loc.clues == initial_loc_clues - 1

    def test_no_extra_clue_on_failure(self, setup):
        state, bus, bag, engine, inv, loc = setup
        bag.tokens = [ChaosTokenType.AUTO_FAIL]
        initial_clues = inv.clues
        initial_loc_clues = loc.clues

        engine.run_test(
            investigator_id="inv1",
            skill_type=Skill.INTELLECT,
            difficulty=2,
            committed_card_ids=["deduction_lv0"],
        )
        assert inv.clues == initial_clues
        assert loc.clues == initial_loc_clues

    def test_no_extra_clue_if_no_clues_left(self, setup):
        state, bus, bag, engine, inv, loc = setup
        bag.tokens = [ChaosTokenType.PLUS_1]
        loc.clues = 0

        engine.run_test(
            investigator_id="inv1",
            skill_type=Skill.INTELLECT,
            difficulty=2,
            committed_card_ids=["deduction_lv0"],
        )
        assert inv.clues == 0
        assert loc.clues == 0

    def test_not_triggered_for_combat(self, setup):
        """Deduction only triggers on intellect tests."""
        state, bus, bag, engine, inv, loc = setup
        bag.tokens = [ChaosTokenType.PLUS_1]
        initial_loc_clues = loc.clues

        engine.run_test(
            investigator_id="inv1",
            skill_type=Skill.COMBAT,
            difficulty=2,
            committed_card_ids=["deduction_lv0"],
        )
        # No clue gained — wrong skill type
        assert loc.clues == initial_loc_clues


class TestDeductionInvestigateAction:
    """真实调查行动流程：基础发现先结算，推理额外线索在其后。"""

    @pytest.fixture
    def game(self):
        from backend.engine.game import Game
        from backend.models.enums import CardType, PlayerClass
        from backend.models.state import CardData

        g = Game("test_deduction_action")
        g.chaos_bag.seed(42)

        inv_data = make_investigator_data(intellect=5)
        g.register_card_data(inv_data)

        loc_data = make_location_data(shroud=3)
        g.register_card_data(loc_data)

        g.register_card_data(CardData(
            id="deduction_lv0", name="Deduction", name_cn="推理",
            type=CardType.SKILL, card_class=PlayerClass.SEEKER,
            skill_icons={"intellect": 1},
        ))

        g.add_investigator("inv1", inv_data, starting_location="test_location")
        g.add_location("test_location", loc_data, clues=2)
        g.card_registry.register_class(Deduction)
        return g

    def _investigate(self, game):
        inv = game.state.get_investigator("inv1")
        inv.actions_remaining = 3
        game.action_resolver.perform_action(
            "inv1", Action.INVESTIGATE, committed_cards=["deduction_lv0"],
        )

    def test_two_clues_gained_with_two_on_location(self, game):
        """技能5 vs 难度3：基础1 + 推理1 = 共拿2条（用户场景）。"""
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]
        loc = game.state.get_location("test_location")
        inv = game.state.get_investigator("inv1")
        self._investigate(game)
        assert inv.clues == 2
        assert loc.clues == 0

    def test_base_clue_first_when_one_left(self, game):
        """只剩1条线索：基础发现优先拿到（不为负），推理无额外可取。"""
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]
        loc = game.state.get_location("test_location")
        loc.clues = 1
        inv = game.state.get_investigator("inv1")
        self._investigate(game)
        assert inv.clues == 1
        assert loc.clues == 0
        assert loc.clues >= 0  # 地点线索不能为负

    def test_clue_discovered_event_fires_for_base(self, game):
        """基础发现的 CLUE_DISCOVERED 事件必须触发（米兰博士等依赖它）。"""
        from backend.models.enums import GameEvent
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]
        seen = []

        def spy(ctx):
            seen.append(ctx.amount)

        game.event_bus.register(
            GameEvent.CLUE_DISCOVERED, spy,
            priority=__import__("backend.models.enums", fromlist=["TimingPriority"]).TimingPriority.AFTER,
        )
        loc = game.state.get_location("test_location")
        loc.clues = 1
        self._investigate(game)
        assert seen == [1]  # 基础发现触发了一次
