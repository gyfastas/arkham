"""Tests for Pnakotic Manuscripts (Level 5).

官方：使用(3秘密)。[反应]同地点调查员将在显现效果中检定时，花1秘密：
该检定不抽标记。[行动]花1秘密：选择同地点1位调查员，其本轮下次检定
不抽标记。（"不抽标记"以标记修正归零+取消自动失败实现，见实现说明。）
"""

import pytest

from backend.cards.seeker.pnakotic_manuscripts_lv5 import PnakoticManuscripts
from backend.engine.game import Game
from backend.models.enums import ChaosTokenType, Skill
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_asset_data, make_investigator_data, make_location_data,
)


@pytest.fixture
def game():
    g = Game("test_pnakotic")
    g.chaos_bag.seed(42)

    inv_data = make_investigator_data(willpower=3)
    g.register_card_data(inv_data)
    loc_data = make_location_data(id="loc_a")
    g.register_card_data(loc_data)
    g.add_investigator("player", inv_data, starting_location="loc_a")
    g.add_location("loc_a", loc_data, clues=0)

    g.register_card_data(make_asset_data(
        id="pnakotic_manuscripts_lv5", name="Pnakotic Manuscripts",
        cost=5, uses={"secretss": 3},  # 数据笔误键名
    ))
    inst = CardInstance(
        instance_id="inst_pm", card_id="pnakotic_manuscripts_lv5",
        owner_id="player", controller_id="player",
    )
    inst.uses = {"secretss": 3}
    g.state.cards_in_play["inst_pm"] = inst
    g.state.get_investigator("player").play_area.append("inst_pm")

    impl = PnakoticManuscripts("inst_pm")
    impl.register(g.event_bus, "inst_pm")
    return g, impl


class TestPnakoticManuscripts:
    def test_action_skips_next_test_token(self, game):
        """[行动]花1秘密：下次检定不抽标记（自动失败标记被跳过→正常计值）。"""
        g, impl = game
        inst = g.state.get_card_instance("inst_pm")
        assert impl.activate(g.state, "player") is True
        assert inst.uses["secretss"] == 2

        g.chaos_bag.tokens = [ChaosTokenType.AUTO_FAIL]
        result = g.skill_test_engine.run_test(
            investigator_id="player", skill_type=Skill.WILLPOWER,
            difficulty=3,
        )
        # 自动失败被跳过：3 >= 3 成功
        assert result.success is True
        assert result.auto_fail is False

    def test_negative_token_nullified(self, game):
        """-3标记被跳过：修正归零（3 >= 3 成功）。"""
        g, impl = game
        assert impl.skip_revelation_test(g.state, "player") is True
        g.chaos_bag.tokens = [ChaosTokenType.MINUS_3]
        result = g.skill_test_engine.run_test(
            investigator_id="player", skill_type=Skill.WILLPOWER,
            difficulty=3,
        )
        assert result.success is True
        assert result.token_modifier == 0

    def test_no_secrets_cannot_activate(self, game):
        g, impl = game
        inst = g.state.get_card_instance("inst_pm")
        inst.uses["secretss"] = 0
        assert impl.activate(g.state, "player") is False

    def test_armed_expires_at_round_end(self, game):
        """本轮未检定：武装在轮末清除（下轮不再生效）。"""
        from backend.engine.event_bus import EventContext
        from backend.models.enums import GameEvent
        g, impl = game
        assert impl.activate(g.state, "player") is True
        g.event_bus.emit(EventContext(
            game_state=g.state, event=GameEvent.ROUND_ENDS))
        g.chaos_bag.tokens = [ChaosTokenType.AUTO_FAIL]
        result = g.skill_test_engine.run_test(
            investigator_id="player", skill_type=Skill.WILLPOWER,
            difficulty=3,
        )
        assert result.success is False  # 自动失败正常生效
