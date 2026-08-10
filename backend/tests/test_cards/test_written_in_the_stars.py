"""Tests for Written in the Stars (Level 0).

官方：快速。只能在你的回合中打出。丢弃你牌堆顶部的卡牌。若是弱点，
混洗回牌堆。否则本回合剩余时间内，只要该卡在弃牌堆中，将其投入到
你执行的每个符合条件的技能检定中。
"""

import pytest

from backend.cards.seeker.written_in_the_stars_lv0 import WrittenInTheStars
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import ChaosTokenType, GameEvent, Skill
from backend.models.state import CardData
from backend.models.enums import CardType, PlayerClass
from backend.tests.conftest import (
    make_investigator_data, make_location_data, make_skill_data,
)


@pytest.fixture
def game():
    g = Game("test_written_in_the_stars")
    g.chaos_bag.seed(42)
    g.chaos_bag.tokens = [ChaosTokenType.ZERO]

    inv_data = make_investigator_data(intellect=3, combat=3)
    g.register_card_data(inv_data)
    loc_data = make_location_data(id="loc_a")
    g.register_card_data(loc_data)
    g.add_investigator(
        "player", inv_data, deck=["guts_lv0"], starting_location="loc_a")
    g.add_location("loc_a", loc_data, clues=0)

    # 顶牌：2意志图标
    g.register_card_data(CardData(
        id="guts_lv0", name="Guts", name_cn="胆识", type=CardType.SKILL,
        card_class=PlayerClass.MYSTIC, skill_icons={"willpower": 2},
    ))
    g.card_registry.register_class(WrittenInTheStars)
    g.card_registry.activate_card(
        "written_in_the_stars_lv0", "impl_wits", g.event_bus,
        chaos_bag=g.chaos_bag)
    return g


def _play(game):
    ctx = EventContext(
        game_state=game.state, event=GameEvent.CARD_PLAYED,
        investigator_id="player",
        extra={"card_id": "written_in_the_stars_lv0"},
    )
    game.event_bus.emit(ctx)
    return ctx


class TestWrittenInTheStars:
    def test_discarded_card_commits_to_each_test(self, game):
        """弃到胆识：本回合你的每个意志检定+2图标（可多次）。"""
        inv = game.state.get_investigator("player")
        ctx = _play(game)
        assert ctx.extra.get("written_in_the_stars_card") == "guts_lv0"
        assert "guts_lv0" in inv.discard
        assert inv.deck == []

        r1 = game.skill_test_engine.run_test(
            investigator_id="player", skill_type=Skill.WILLPOWER,
            difficulty=5,
        )
        assert r1.committed_icons == 2
        assert r1.success is True  # 3+2=5
        # 第二次检定仍然生效（每个符合条件的检定）
        r2 = game.skill_test_engine.run_test(
            investigator_id="player", skill_type=Skill.WILLPOWER,
            difficulty=5,
        )
        assert r2.committed_icons == 2
        # 战斗检定不符合条件（无匹配/wild图标）：+0
        r3 = game.skill_test_engine.run_test(
            investigator_id="player", skill_type=Skill.COMBAT,
            difficulty=3,
        )
        assert r3.committed_icons == 0

    def test_weakness_shuffled_back(self, game):
        """弃到弱点：混洗回牌堆，不入弃牌堆。"""
        inv = game.state.get_investigator("player")
        game.register_card_data(CardData(
            id="chronophobia_lv0", name="Chronophobia", name_cn="时间恐惧症",
            type=CardType.TREACHERY, subtype="weakness",
        ))
        inv.deck = ["chronophobia_lv0"]
        ctx = _play(game)
        assert ctx.extra.get("written_in_the_stars_weakness") == "chronophobia_lv0"
        assert "chronophobia_lv0" in inv.deck
        assert inv.discard == []
