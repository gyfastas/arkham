"""Tests for The Stygian Eye (Level 3).

官方：快速。只能在你的回合中打出。混乱袋内每有1个[curse]标记，打出
费用减1。直到本轮结束，你的每项技能+3。
（费用减免经 current_cost() 供会话层结算，见实现说明。）
"""

import pytest

from backend.cards.seeker.the_stygian_eye_lv3 import TheStygianEye
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import ChaosTokenType, GameEvent, Skill
from backend.tests.conftest import (
    make_investigator_data, make_location_data,
)


@pytest.fixture
def game():
    g = Game("test_stygian_eye")
    g.chaos_bag.seed(42)
    g.chaos_bag.tokens = [ChaosTokenType.ZERO]

    inv_data = make_investigator_data(willpower=2, intellect=2)
    g.register_card_data(inv_data)
    loc_data = make_location_data(id="loc_a")
    g.register_card_data(loc_data)
    g.add_investigator("player", inv_data, starting_location="loc_a")
    g.add_location("loc_a", loc_data, clues=0)

    g.card_registry.register_class(TheStygianEye)
    g.card_registry.activate_card(
        "the_stygian_eye_lv3", "impl_eye", g.event_bus,
        chaos_bag=g.chaos_bag)
    return g


def _play(game):
    ctx = EventContext(
        game_state=game.state, event=GameEvent.CARD_PLAYED,
        investigator_id="player",
        extra={"card_id": "the_stygian_eye_lv3"},
    )
    game.event_bus.emit(ctx)
    return ctx


class TestTheStygianEye:
    def test_cost_reduced_per_curse(self, game):
        """袋中每个诅咒标记费用-1（10-3=7）。"""
        for _ in range(3):
            game.chaos_bag.add_token(ChaosTokenType.CURSE)
        assert TheStygianEye.current_cost(game.chaos_bag) == 7

    def test_plus_three_all_skills_until_round_ends(self, game):
        """打出后：你的各项检定+3（2+3=5过难度5）；本轮结束失效。"""
        _play(game)
        result = game.skill_test_engine.run_test(
            investigator_id="player", skill_type=Skill.WILLPOWER,
            difficulty=5,
        )
        assert result.success is True
        sources = result.extra.get("skill_bonus_sources", [])
        assert any(s["reason"] == "stygian_eye_boost" and s["delta"] == 3
                   for s in sources)

        game.event_bus.emit(EventContext(
            game_state=game.state, event=GameEvent.ROUND_ENDS))
        result2 = game.skill_test_engine.run_test(
            investigator_id="player", skill_type=Skill.INTELLECT,
            difficulty=5,
        )
        assert result2.success is False  # 2 < 5，加值已过期
