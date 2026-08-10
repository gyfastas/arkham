"""Tests for Dig Deep (Level 4)."""

import pytest

from backend.cards.survivor.dig_deep_lv4 import DigDeepLv4
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import Action, ChaosTokenType, GameEvent, Skill
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
    # 数据文件键名为 "resourcess"（笔误），实现两种键名兼容
    g.register_card_data(make_asset_data(
        id="dig_deep_lv4", name="Dig Deep", cost=2,
        traits=["talent"], uses={"resourcess": 2}))
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)
    g.card_registry.register_class(DigDeepLv4)
    return g


def _play_dig_deep(game):
    inv = game.state.get_investigator("inv1")
    inv.resources = 5
    inv.hand = ["dig_deep_lv4"]
    assert game.action_resolver.perform_action(
        "inv1", Action.PLAY, card_id="dig_deep_lv4") is True
    iid = next(i for i in inv.play_area
               if game.state.get_card_instance(i).card_id == "dig_deep_lv4")
    return inv, iid, game.card_registry.active_instances[iid]


class TestDigDeepLv4:
    def test_card_registered(self, game):
        assert "dig_deep_lv4" in game.card_registry.registered_cards

    def test_spend_card_resources_first_then_pool(self, game):
        """优先花深挖上的资源，用尽后花资源池；加值可叠加。"""
        inv, iid, impl = _play_dig_deep(game)
        assert impl.spend(game.state, "inv1", Skill.WILLPOWER) is True
        assert impl.spend(game.state, "inv1", Skill.WILLPOWER) is True
        inst = game.state.get_card_instance(iid)
        assert inst.uses["resourcess"] == 0

        # 卡上资源用尽：第三次花费走资源池
        resources_before = inv.resources
        assert impl.spend(game.state, "inv1", Skill.WILLPOWER) is True
        assert inv.resources == resources_before - 1

        game.chaos_bag.tokens = [ChaosTokenType.ZERO]
        result = game.skill_test_engine.run_test("inv1", Skill.WILLPOWER, 6)
        assert result.modified_skill == 6  # 3基础 + 3次加值
        assert result.success is True

    def test_replenish_at_round_begins(self, game):
        """每轮开始：补满卡上的2个资源。"""
        inv, iid, impl = _play_dig_deep(game)
        impl.spend(game.state, "inv1", Skill.AGILITY)
        inst = game.state.get_card_instance(iid)
        assert inst.uses["resourcess"] == 1
        game.event_bus.emit(EventContext(
            game_state=game.state, event=GameEvent.ROUND_BEGINS))
        assert inst.uses["resourcess"] == 2
