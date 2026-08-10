"""Tests for Analytical Mind (Level 0) — Minh Thi Phan signature asset."""

from backend.cards.neutral.analytical_mind_lv0 import AnalyticalMind
from backend.models.enums import ChaosTokenType, Skill
from backend.models.state import CardInstance
from backend.tests.conftest import make_skill_data


def _setup(game):
    game.register_card_data(make_skill_data(id="guts_lv0", skill_icons={"willpower": 2}))
    game.register_card_data(make_skill_data(id="perception_lv0", skill_icons={"intellect": 2}))
    inv = game.state.get_investigator("test_investigator")
    inv.deck = ["d1", "d2", "d3"]

    inst = CardInstance(
        instance_id="am1", card_id="analytical_mind_lv0",
        owner_id="test_investigator", controller_id="test_investigator",
    )
    game.state.cards_in_play["am1"] = inst
    inv.play_area.append("am1")
    impl = AnalyticalMind("am1")
    impl.register(game.event_bus, "am1")
    return impl, inv, inst


class TestAnalyticalMind:
    def test_exactly_one_commit_exhausts_and_draws(self, game):
        """投入正好1张卡 → 消耗并抽1张。"""
        impl, inv, inst = _setup(game)
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]
        game.skill_test_engine.run_test(
            "test_investigator", Skill.WILLPOWER, 3,
            committed_card_ids=["guts_lv0"],
        )
        assert inst.exhausted
        assert len(inv.hand) == 1
        assert len(inv.deck) == 2

    def test_two_commits_no_trigger(self, game):
        impl, inv, inst = _setup(game)
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]
        game.skill_test_engine.run_test(
            "test_investigator", Skill.WILLPOWER, 3,
            committed_card_ids=["guts_lv0", "perception_lv0"],
        )
        assert not inst.exhausted
        assert len(inv.deck) == 3

    def test_zero_commits_no_trigger(self, game):
        impl, inv, inst = _setup(game)
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]
        game.skill_test_engine.run_test("test_investigator", Skill.WILLPOWER, 3)
        assert not inst.exhausted

    def test_exhausted_no_double_trigger(self, game):
        impl, inv, inst = _setup(game)
        inst.exhausted = True
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]
        game.skill_test_engine.run_test(
            "test_investigator", Skill.WILLPOWER, 3,
            committed_card_ids=["guts_lv0"],
        )
        assert len(inv.deck) == 3

    def test_other_investigator_test_no_trigger(self, game):
        """别人的检定（非拥有者）不触发。"""
        from backend.tests.conftest import make_investigator_data
        impl, inv, inst = _setup(game)
        other = make_investigator_data(id="other")
        game.register_card_data(other)
        game.add_investigator("other", other, starting_location="test_location")
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]
        game.skill_test_engine.run_test(
            "other", Skill.WILLPOWER, 3, committed_card_ids=["guts_lv0"],
        )
        assert not inst.exhausted

    def test_can_commit_to_other_location(self, game):
        impl, inv, inst = _setup(game)
        assert impl.can_commit_to_other_location(game.state, "test_investigator") is True
        assert impl.can_commit_to_other_location(game.state, "other") is False
