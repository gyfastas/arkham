"""Tests for Prophesiae Profana (Level 5).

官方：只要你没位于座标点，+1[intellect]、+1[agility]，可忽略趁乱攻击。
[反应]入场后：选择一个已揭示地点为"座标点"。[行动]：移动任一位调查员
到座标点。
"""

import pytest

from backend.cards.seeker.prophesiae_profana_lv5 import ProphesiaeProfana
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import ChaosTokenType, GameEvent, Skill
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_asset_data, make_investigator_data, make_location_data,
)


@pytest.fixture
def game():
    g = Game("test_prophesiae")
    g.chaos_bag.seed(42)
    g.chaos_bag.tokens = [ChaosTokenType.ZERO]

    inv_data = make_investigator_data(intellect=3, agility=3)
    g.register_card_data(inv_data)
    loc_a = make_location_data(id="loc_a", connections=["loc_b"])
    loc_b = make_location_data(id="loc_b", connections=["loc_a"])
    g.register_card_data(loc_a)
    g.register_card_data(loc_b)
    g.add_investigator("player", inv_data, starting_location="loc_a")
    g.add_location("loc_a", loc_a, clues=0)
    g.add_location("loc_b", loc_b, clues=0)
    g.state.get_location("loc_a").revealed = True
    g.state.get_location("loc_b").revealed = True

    g.register_card_data(make_asset_data(
        id="prophesiae_profana_lv5", name="Prophesiae Profana", cost=4))
    inst = CardInstance(
        instance_id="inst_pp", card_id="prophesiae_profana_lv5",
        owner_id="player", controller_id="player",
    )
    g.state.cards_in_play["inst_pp"] = inst
    g.state.get_investigator("player").play_area.append("inst_pp")

    impl = ProphesiaeProfana("inst_pp")
    impl.register(g.event_bus, "inst_pp")
    # 模拟入场事件（预设座标点为 loc_b）
    impl.set_locus(g.state, "loc_b")
    impl._pending_locus = "loc_b"
    g.event_bus.emit(EventContext(
        game_state=g.state, event=GameEvent.CARD_ENTERS_PLAY,
        investigator_id="player", target="inst_pp",
        extra={"card_id": "prophesiae_profana_lv5"},
    ))
    return g, impl


class TestProphesiaeProfana:
    def test_locus_chosen_on_enter(self, game):
        """入场后：预置的已揭示地点成为座标点。"""
        g, _impl = game
        assert g.state.scenario.vars.get("prophesiae_profana_locus") == "loc_b"

    def test_skill_bonus_off_locus(self, game):
        """不在座标点（在loc_a）：智力检定+1。"""
        g, _impl = game
        result = g.skill_test_engine.run_test(
            investigator_id="player", skill_type=Skill.INTELLECT,
            difficulty=4,
        )
        assert result.success is True  # 3+1=4
        sources = result.extra.get("skill_bonus_sources", [])
        assert any(s["reason"] == "prophesiae_profana_bonus" for s in sources)

    def test_no_bonus_at_locus(self, game):
        """在座标点：无加值。"""
        g, _impl = game
        inv = g.state.get_investigator("player")
        inv.location_id = "loc_b"
        result = g.skill_test_engine.run_test(
            investigator_id="player", skill_type=Skill.INTELLECT,
            difficulty=4,
        )
        assert result.success is False  # 3 < 4

    def test_ignores_attack_of_opportunity_off_locus(self, game):
        """不在座标点：趁乱攻击被取消。"""
        g, _impl = game
        ctx = EventContext(
            game_state=g.state, event=GameEvent.ATTACK_OF_OPPORTUNITY,
            investigator_id="player", enemy_id="enemy_x",
        )
        g.event_bus.emit(ctx)
        assert ctx.cancelled is True

    def test_move_investigator_to_locus(self, game):
        """[行动]：移动调查员到座标点。"""
        g, impl = game
        inv = g.state.get_investigator("player")
        assert impl.activate(g.state, "player") is True
        assert inv.location_id == "loc_b"
