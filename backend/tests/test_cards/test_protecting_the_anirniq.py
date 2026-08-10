"""Tests for Protecting the Anirniq (Level 2).

官方：快速。在你所在地点一张[[盟友]]支援卡被卡牌效果丢弃或被击败后打出。
将该支援卡返回其所有者的手中，或其所有者抽取3张卡牌。
"""

import pytest

from backend.cards.seeker.protecting_the_anirniq_lv2 import ProtectingTheAnirniq
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import GameEvent
from backend.tests.conftest import (
    make_asset_data, make_investigator_data, make_location_data,
)


@pytest.fixture
def game():
    g = Game("test_anirniq")
    g.chaos_bag.seed(42)

    inv_data = make_investigator_data()
    g.register_card_data(inv_data)
    loc_data = make_location_data(id="loc_a")
    g.register_card_data(loc_data)
    g.add_investigator(
        "player", inv_data, deck=["card_a", "card_b", "card_c"],
        starting_location="loc_a",
    )
    g.add_location("loc_a", loc_data, clues=0)

    g.register_card_data(make_asset_data(
        id="art_student_lv0", name="Art Student", traits=["ally"]))
    g.register_card_data(make_asset_data(
        id="magnifying_glass_lv0", name="Magnifying Glass", traits=["item"]))
    g.card_registry.register_class(ProtectingTheAnirniq)
    g.card_registry.activate_card(
        "protecting_the_anirniq_lv2", "impl_anirniq", g.event_bus,
        chaos_bag=g.chaos_bag)
    return g


def _play(game, **extra):
    ctx = EventContext(
        game_state=game.state, event=GameEvent.CARD_PLAYED,
        investigator_id="player",
        extra={"card_id": "protecting_the_anirniq_lv2", **extra},
    )
    game.event_bus.emit(ctx)
    return ctx


class TestProtectingTheAnirniq:
    def test_returns_discarded_ally_to_hand(self, game):
        """默认：弃牌堆中最近的盟友支援返回所有者手牌。"""
        inv = game.state.get_investigator("player")
        inv.discard = ["magnifying_glass_lv0", "art_student_lv0"]
        ctx = _play(game)
        assert ctx.extra.get("anirniq_mode_used") == "return"
        assert "art_student_lv0" in inv.hand
        assert "art_student_lv0" not in inv.discard

    def test_draw_mode_draws_three(self, game):
        """draw 模式：所有者抽3张牌。"""
        inv = game.state.get_investigator("player")
        inv.discard = ["art_student_lv0"]
        hand_before = list(inv.hand)
        ctx = _play(game, anirniq_mode="draw")
        assert ctx.extra.get("anirniq_mode_used") == "draw"
        assert "art_student_lv0" in inv.discard  # 留在弃牌堆
        assert inv.hand == hand_before + ["card_a", "card_b", "card_c"]
        assert inv.deck == []

    def test_no_ally_no_effect(self, game):
        """弃牌堆无盟友：效果落空。"""
        inv = game.state.get_investigator("player")
        inv.discard = ["magnifying_glass_lv0"]
        ctx = _play(game)
        assert ctx.extra.get("anirniq_failed") == "no_ally"
        assert "magnifying_glass_lv0" not in inv.hand
