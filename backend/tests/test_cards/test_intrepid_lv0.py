"""Tests for Intrepid (Level 0). (04192)

检定成功后放置入场为支援：+1智力/+1战斗/+1敏捷；回合结束时丢弃。
"""

import pytest
from backend.cards.guardian.intrepid_lv0 import Intrepid
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import (
    ChaosTokenType, GameEvent, PlayerClass, Skill,
)
from backend.tests.conftest import (
    make_investigator_data, make_location_data, make_skill_data,
)


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)
    inv_data = make_investigator_data(willpower=3)
    g.register_card_data(inv_data)
    g.register_card_data(make_location_data())
    g.register_card_data(make_skill_data(
        id="intrepid_lv0", name="Intrepid",
        card_class=PlayerClass.GUARDIAN, skill_icons={"willpower": 1},
    ))
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", g.state.get_card_data("test_location"), clues=0)
    g.card_registry.register_class(Intrepid)

    inv = g.state.get_investigator("inv1")
    inv.hand.append("intrepid_lv0")
    return g


class TestIntrepid:
    def test_enters_play_on_success_and_grants_bonuses(self, game):
        """投入并成功：入场（不弃置），提供三项+1。"""
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]
        result = game.skill_test_engine.run_test(
            investigator_id="inv1",
            skill_type=Skill.WILLPOWER,
            difficulty=2,
            committed_card_ids=["intrepid_lv0"],
        )
        assert result.success is True
        inv = game.state.get_investigator("inv1")
        # 入场而非弃置
        assert "intrepid_lv0" not in inv.hand
        assert "intrepid_lv0" not in inv.discard
        assert len(inv.play_area) == 1
        inst = game.state.get_card_instance(inv.play_area[0])
        assert inst.card_id == "intrepid_lv0"
        # 场上提供 +1智力/+1战斗/+1敏捷（重新注册的实现生效）
        bonuses = game.preview_skill_bonuses("inv1")
        assert bonuses.get("intellect") == 1
        assert bonuses.get("combat") == 1
        assert bonuses.get("agility") == 1
        assert "willpower" not in bonuses

    def test_discarded_at_round_end(self, game):
        """回合结束：丢弃无畏。"""
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]
        game.skill_test_engine.run_test(
            investigator_id="inv1",
            skill_type=Skill.WILLPOWER,
            difficulty=2,
            committed_card_ids=["intrepid_lv0"],
        )
        inv = game.state.get_investigator("inv1")
        assert len(inv.play_area) == 1

        game.event_bus.emit(EventContext(
            game_state=game.state, event=GameEvent.ROUND_ENDS,
        ))
        assert len(inv.play_area) == 0
        assert "intrepid_lv0" in inv.discard

    def test_stays_in_hand_on_failure(self, game):
        """检定失败：正常弃置（不入场）。"""
        game.chaos_bag.tokens = [ChaosTokenType.MINUS_4]
        result = game.skill_test_engine.run_test(
            investigator_id="inv1",
            skill_type=Skill.WILLPOWER,
            difficulty=5,
            committed_card_ids=["intrepid_lv0"],
        )
        assert result.success is False
        inv = game.state.get_investigator("inv1")
        assert len(inv.play_area) == 0
        assert "intrepid_lv0" in inv.discard  # 引擎 ST.8 正常弃置
