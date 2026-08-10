"""Tests for The King in Yellow (Level 0) — Minh Thi Phan signature weakness."""

from backend.cards.neutral.the_king_in_yellow_lv0 import TheKingInYellow
from backend.engine.event_bus import EventContext
from backend.models.enums import ChaosTokenType, GameEvent, Skill
from backend.tests.conftest import make_skill_data


def _reveal(game):
    impl = TheKingInYellow("k1")
    impl.register(game.event_bus, "k1")
    inv = game.state.get_investigator("test_investigator")
    inv.hand.append("the_king_in_yellow_lv0")
    ctx = EventContext(
        game_state=game.state, event=GameEvent.CARD_DRAWN,
        investigator_id="test_investigator",
        extra={"card_id": "the_king_in_yellow_lv0"},
    )
    game.event_bus.emit(ctx)
    return impl, inv


class TestTheKingInYellow:
    def test_revelation_enters_threat_area(self, game):
        impl, inv = _reveal(game)
        assert "the_king_in_yellow_lv0" not in inv.hand
        assert len(inv.threat_area) == 1

    def test_commit_restriction(self, game):
        """不能投入正好1或2张卡。"""
        impl, inv = _reveal(game)
        assert impl.can_commit(game.state, "test_investigator", 0) is True
        assert impl.can_commit(game.state, "test_investigator", 1) is False
        assert impl.can_commit(game.state, "test_investigator", 2) is False
        assert impl.can_commit(game.state, "test_investigator", 3) is True

    def test_discarded_after_success_with_6_matching_icons(self, game):
        """成功检定投入6个对应图标（含狂野）→ 丢弃。"""
        impl, inv = _reveal(game)
        for i in range(3):
            game.register_card_data(make_skill_data(
                id=f"skill_{i}", skill_icons={"intellect": 1, "wild": 1}))
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]  # 3+6=9 vs 3 成功
        game.skill_test_engine.run_test(
            "test_investigator", Skill.INTELLECT, 3,
            committed_card_ids=["skill_0", "skill_1", "skill_2"],
        )
        assert inv.threat_area == []
        assert "the_king_in_yellow_lv0" in inv.discard

    def test_stays_with_fewer_icons(self, game):
        impl, inv = _reveal(game)
        game.register_card_data(make_skill_data(
            id="skill_0", skill_icons={"intellect": 2}))
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]
        game.skill_test_engine.run_test(
            "test_investigator", Skill.INTELLECT, 3,
            committed_card_ids=["skill_0"],
        )
        assert len(inv.threat_area) == 1

    def test_stays_on_failed_test(self, game):
        impl, inv = _reveal(game)
        for i in range(3):
            game.register_card_data(make_skill_data(
                id=f"skill_{i}", skill_icons={"intellect": 2}))
        game.chaos_bag.tokens = [ChaosTokenType.AUTO_FAIL]
        game.skill_test_engine.run_test(
            "test_investigator", Skill.INTELLECT, 3,
            committed_card_ids=["skill_0", "skill_1", "skill_2"],
        )
        assert len(inv.threat_area) == 1
