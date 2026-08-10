"""Tests for Practice Makes Perfect (Level 0).

官方：快速。在你所在地点的技能检定中打出。检索牌堆顶9张中的1张
[[精通]]技能卡并投入本次检定；其余洗回牌堆。检定结束后若成功，该
技能卡加入手牌而非弃置。
"""

import pytest

from backend.cards.seeker.practice_makes_perfect_lv0 import PracticeMakesPerfect
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import ChaosTokenType, GameEvent, Skill
from backend.tests.conftest import (
    make_investigator_data, make_location_data, make_skill_data,
)


@pytest.fixture
def game():
    g = Game("test_pmp")
    g.chaos_bag.seed(42)
    g.chaos_bag.tokens = [ChaosTokenType.ZERO]

    inv_data = make_investigator_data(intellect=3)
    g.register_card_data(inv_data)
    loc_data = make_location_data(id="loc_a")
    g.register_card_data(loc_data)
    g.add_investigator(
        "player", inv_data,
        deck=["card_x", "deduction_lv0", "card_y"],
        starting_location="loc_a",
    )
    g.add_location("loc_a", loc_data, clues=0)

    from backend.models.enums import CardType, PlayerClass
    from backend.models.state import CardData
    g.register_card_data(CardData(
        id="practice_makes_perfect_lv0", name="Practice Makes Perfect",
        name_cn="熟能生巧", type=CardType.EVENT,
        card_class=PlayerClass.SEEKER, cost=1, fast=True,
    ))
    # 精通技能卡：2智力图标
    g.register_card_data(CardData(
        id="deduction_lv0", name="Deduction", name_cn="演绎法",
        type=CardType.SKILL, card_class=PlayerClass.SEEKER,
        skill_icons={"intellect": 2}, traits=["practiced"],
    ))
    g.register_card_data(make_skill_data(id="card_x", skill_icons={"wild": 1}))
    g.register_card_data(make_skill_data(id="card_y", skill_icons={"wild": 1}))
    g.card_registry.register_class(PracticeMakesPerfect)
    impl = g.card_registry.activate_card(
        "practice_makes_perfect_lv0", "impl_pmp", g.event_bus,
        chaos_bag=g.chaos_bag)
    return g, impl


def _play(game, **extra):
    ctx = EventContext(
        game_state=game.state, event=GameEvent.CARD_PLAYED,
        investigator_id="player",
        extra={"card_id": "practice_makes_perfect_lv0", **extra},
    )
    game.event_bus.emit(ctx)
    return ctx


class TestPracticeMakesPerfect:
    def test_search_commit_and_return_on_success(self, game):
        """找到演绎法投入检定（+2智力图标），成功后演绎法加入手牌。"""
        g, _impl = game
        inv = g.state.get_investigator("player")
        ctx = _play(g)
        assert ctx.extra.get("practice_makes_perfect_committed") == "deduction_lv0"
        assert "deduction_lv0" not in inv.deck

        # 智力3 + 2(演绎法图标) = 5 过难度5
        result = g.skill_test_engine.run_test(
            investigator_id="player", skill_type=Skill.INTELLECT,
            difficulty=5,
        )
        assert result.success is True
        assert "deduction_lv0" in inv.hand
        assert "deduction_lv0" not in inv.discard

    def test_failure_discards_skill(self, game):
        """检定失败：精通技能卡弃置。"""
        g, _impl = game
        inv = g.state.get_investigator("player")
        _play(g)
        g.chaos_bag.tokens = [ChaosTokenType.AUTO_FAIL]
        result = g.skill_test_engine.run_test(
            investigator_id="player", skill_type=Skill.INTELLECT,
            difficulty=5,
        )
        assert result.success is False
        assert "deduction_lv0" in inv.discard
        assert "deduction_lv0" not in inv.hand

    def test_no_practiced_skill_no_effect(self, game):
        """顶9张无精通技能卡：效果落空，牌堆不动。"""
        g, _impl = game
        inv = g.state.get_investigator("player")
        inv.deck = ["card_x", "card_y"]
        ctx = _play(g)
        assert ctx.extra.get("practice_makes_perfect_failed") == "no_practiced"
        assert inv.deck == ["card_x", "card_y"]
