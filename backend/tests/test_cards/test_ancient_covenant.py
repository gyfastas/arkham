"""Tests for Ancient Covenant (Level 2)."""

import pytest

from backend.cards.survivor.ancient_covenant_lv2 import AncientCovenant
from backend.engine.game import Game
from backend.models.enums import ChaosTokenType, Skill
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_asset_data, make_investigator_data, make_location_data,
)


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)
    inv_data = make_investigator_data(willpower=3)
    g.register_card_data(inv_data)
    loc = make_location_data()
    g.register_card_data(loc)
    g.register_card_data(make_asset_data(
        id="ancient_covenant_lv2", name="Ancient Covenant", cost=0,
        traits=["covenant", "blessed"]))
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)
    g.card_registry.register_class(AncientCovenant)
    # 直接放置入场并激活实现
    game_inst = CardInstance(
        instance_id="covenant_1", card_id="ancient_covenant_lv2",
        owner_id="inv1", controller_id="inv1",
    )
    g.state.cards_in_play["covenant_1"] = game_inst
    g.state.get_investigator("inv1").play_area.append("covenant_1")
    g.card_registry.activate_card(
        "ancient_covenant_lv2", "covenant_1", g.event_bus,
        chaos_bag=g.chaos_bag)
    return g


class TestAncientCovenant:
    def test_card_registered(self, game):
        assert "ancient_covenant_lv2" in game.card_registry.registered_cards

    def test_bless_resolution_exhausts_covenant(self, game):
        """同地点调查员结算祝福标记：消耗古代圣约并标记不再额外揭示。"""
        game.chaos_bag.tokens = [ChaosTokenType.BLESS]
        inst = game.state.get_card_instance("covenant_1")
        assert inst.exhausted is False

        result = game.skill_test_engine.run_test(
            "inv1", Skill.WILLPOWER, 3)
        # 祝福+2：3基础+2 ≥ 3 成功
        assert result.success is True
        assert inst.exhausted is True

    def test_exhausted_covenant_does_not_trigger(self, game):
        """已消耗的古代圣约不再触发（不重复横置出错）。"""
        inst = game.state.get_card_instance("covenant_1")
        inst.exhausted = True
        game.chaos_bag.tokens = [ChaosTokenType.BLESS]
        # 不抛异常即通过（效果为声明式标记，无从外部观察的副作用）
        result = game.skill_test_engine.run_test(
            "inv1", Skill.WILLPOWER, 3)
        assert result.success is True
        assert inst.exhausted is True
