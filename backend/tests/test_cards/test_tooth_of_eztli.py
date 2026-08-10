"""Tests for Tooth of Eztli (Level 0).

官方：结算诡计卡上的能力时，+1[willpower]、+1[agility]。
[反应]结算诡计卡能力的检定成功后，消耗本卡：抽1张牌。
（"结算诡计卡能力"由会话/剧本层经 begin_treachery_resolution() 告知，
见实现说明。）
"""

import pytest

from backend.cards.seeker.tooth_of_eztli_lv0 import ToothOfEztli
from backend.engine.game import Game
from backend.models.enums import ChaosTokenType, Skill
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_asset_data, make_investigator_data, make_location_data,
)


@pytest.fixture
def game():
    g = Game("test_tooth_of_eztli")
    g.chaos_bag.seed(42)
    g.chaos_bag.tokens = [ChaosTokenType.ZERO]

    inv_data = make_investigator_data(willpower=3, agility=3, combat=3)
    g.register_card_data(inv_data)
    loc_data = make_location_data(id="loc_a")
    g.register_card_data(loc_data)
    g.add_investigator(
        "player", inv_data, deck=["card_a"], starting_location="loc_a")
    g.add_location("loc_a", loc_data, clues=0)

    g.register_card_data(make_asset_data(
        id="tooth_of_eztli_lv0", name="Tooth of Eztli", cost=3,
        traits=["item", "relic"]))
    inst = CardInstance(
        instance_id="inst_tooth", card_id="tooth_of_eztli_lv0",
        owner_id="player", controller_id="player",
    )
    g.state.cards_in_play["inst_tooth"] = inst
    g.state.get_investigator("player").play_area.append("inst_tooth")

    impl = ToothOfEztli("inst_tooth")
    impl.register(g.event_bus, "inst_tooth")
    return g, impl


class TestToothOfEztli:
    def test_treachery_test_bonus_and_draw(self, game):
        """诡计卡检定：意志+1（3+1=4过难度4），成功后消耗抽1张。"""
        g, impl = game
        inv = g.state.get_investigator("player")
        inst = g.state.get_card_instance("inst_tooth")
        impl.begin_treachery_resolution()
        result = g.skill_test_engine.run_test(
            investigator_id="player", skill_type=Skill.WILLPOWER,
            difficulty=4,
        )
        assert result.success is True
        sources = result.extra.get("skill_bonus_sources", [])
        assert any(s["reason"] == "tooth_of_eztli_bonus" and s["delta"] == 1
                   for s in sources)
        assert inst.exhausted is True
        assert "card_a" in inv.hand

    def test_no_bonus_on_normal_test(self, game):
        """非诡计卡检定：无加值、不抽牌。"""
        g, _impl = game
        inv = g.state.get_investigator("player")
        result = g.skill_test_engine.run_test(
            investigator_id="player", skill_type=Skill.WILLPOWER,
            difficulty=4,
        )
        assert result.success is False  # 3 < 4
        assert inv.hand == []

    def test_combat_treachery_test_gets_no_bonus(self, game):
        """诡计卡战斗检定不加（仅意志/敏捷）。"""
        g, impl = game
        impl.begin_treachery_resolution()
        result = g.skill_test_engine.run_test(
            investigator_id="player", skill_type=Skill.COMBAT,
            difficulty=4,
        )
        assert result.success is False  # 3 < 4
