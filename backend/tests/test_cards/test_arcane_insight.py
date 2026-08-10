"""Tests for Arcane Insight (Level 4).

官方：使用(3充能)。[快速]花费1充能：你所在地点-2隐蔽值直到本回合结束。
（每回合限一次。）
"""

import pytest

from backend.cards.seeker.arcane_insight_lv4 import ArcaneInsight
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import ChaosTokenType, GameEvent, Skill
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_asset_data, make_investigator_data, make_location_data,
)


@pytest.fixture
def game():
    g = Game("test_arcane_insight")
    g.chaos_bag.seed(42)

    inv_data = make_investigator_data(intellect=3)
    g.register_card_data(inv_data)
    loc_data = make_location_data(id="loc_a", shroud=4, clue_value=2)
    g.register_card_data(loc_data)
    g.add_investigator("player", inv_data, starting_location="loc_a")
    g.add_location("loc_a", loc_data, clues=2)

    g.register_card_data(make_asset_data(
        id="arcane_insight_lv4", name="Arcane Insight",
        cost=3, uses={"charges": 3}, traits=["spell"],
    ))
    inst = CardInstance(
        instance_id="inst_ai", card_id="arcane_insight_lv4",
        owner_id="player", controller_id="player",
    )
    inst.uses = {"charges": 3}
    g.state.cards_in_play["inst_ai"] = inst
    g.state.get_investigator("player").play_area.append("inst_ai")

    g.card_registry.register_class(ArcaneInsight)
    impl = g.card_registry.activate_card(
        "arcane_insight_lv4", "inst_ai", g.event_bus)
    g.chaos_bag.tokens = [ChaosTokenType.ZERO]
    return g


def _investigate(game):
    return game.skill_test_engine.run_test(
        investigator_id="player", skill_type=Skill.INTELLECT, difficulty=4)


class TestArcaneInsight:
    def test_activate_spends_charge(self, game):
        impl = game.card_registry.active_instances["inst_ai"]
        assert impl.activate(game.state, "player") is True
        inst = game.state.get_card_instance("inst_ai")
        assert inst.uses["charges"] == 2

    def test_shroud_reduced_for_investigate(self, game):
        """隐蔽4：未启动时3智力失败；启动后难度2成功。"""
        impl = game.card_registry.active_instances["inst_ai"]
        assert impl.activate(game.state, "player") is True
        result = _investigate(game)
        assert result.success is True
        assert result.difficulty == 2

    def test_not_armed_no_reduction(self, game):
        result = _investigate(game)
        assert result.success is False

    def test_limit_once_per_turn(self, game):
        impl = game.card_registry.active_instances["inst_ai"]
        assert impl.activate(game.state, "player") is True
        assert impl.activate(game.state, "player") is False
        inst = game.state.get_card_instance("inst_ai")
        assert inst.uses["charges"] == 2  # 第二次未扣充能

    def test_turn_end_resets(self, game):
        """回合结束：隐蔽降低过期，每回合限制复位。"""
        impl = game.card_registry.active_instances["inst_ai"]
        impl.activate(game.state, "player")
        game.event_bus.emit(EventContext(
            game_state=game.state,
            event=GameEvent.INVESTIGATOR_TURN_ENDS,
            investigator_id="player",
        ))
        result = _investigate(game)
        assert result.success is False  # 难度恢复4
        assert impl.activate(game.state, "player") is True  # 下回合可再用
