"""Tests for Eidetic Memory (Level 3).

官方：将本卡作为任意调查员弃牌堆中1张[[Insight]]事件的精确复制打出
（含其资源费用）。将该事件移出游戏。本卡以移出游戏代替弃置。
"""

import pytest

from backend.cards.seeker.eidetic_memory_lv3 import EideticMemory
from backend.cards.seeker.no_stone_unturned_lv0 import NoStoneUnturned
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import Action, CardType, GameEvent, PlayerClass
from backend.models.state import CardData
from backend.tests.conftest import (
    make_event_data, make_investigator_data, make_location_data,
)


def _insight_event_data(card_id, cost):
    return CardData(
        id=card_id, name="No Stone Unturned", name_cn="翻箱倒柜",
        type=CardType.EVENT, card_class=PlayerClass.SEEKER,
        cost=cost, traits=["insight"], skill_icons={"wild": 1},
    )


@pytest.fixture
def game():
    g = Game("test_eidetic_memory")
    g.chaos_bag.seed(42)

    inv_data = make_investigator_data()
    g.register_card_data(inv_data)
    loc_data = make_location_data(id="loc_a", clue_value=2)
    g.register_card_data(loc_data)
    g.add_investigator(
        "player", inv_data,
        deck=["card_a", "card_b", "card_c", "card_d"],
        starting_location="loc_a",
    )
    g.add_location("loc_a", loc_data, clues=2)

    g.register_card_data(make_event_data(id="eidetic_memory_lv3", cost=0))
    g.register_card_data(_insight_event_data("no_stone_unturned_lv0", cost=2))
    g.card_registry.register_class(EideticMemory)
    g.card_registry.register_class(NoStoneUnturned)

    inv = g.state.get_investigator("player")
    inv.hand = ["eidetic_memory_lv3"]
    inv.discard = ["no_stone_unturned_lv0"]
    inv.resources = 5
    inv.actions_remaining = 3
    return g


class TestEideticMemory:
    def test_copies_insight_event_from_discard(self, game):
        """复制弃牌堆中的翻箱倒柜：支付其费用、应用其效果、移出游戏。"""
        inv = game.state.get_investigator("player")
        ok = game.action_resolver.perform_action(
            "player", Action.PLAY, card_id="eidetic_memory_lv3")
        assert ok is True

        # 支付被复制事件的2资源费用
        assert inv.resources == 3
        # 被复制事件效果生效：检索牌库顶6张抽到 card_a
        assert "card_a" in inv.hand
        # 被复制事件移出游戏
        assert "no_stone_unturned_lv0" not in inv.discard
        removed = game.state.scenario.vars["removed_from_game"]
        assert "no_stone_unturned_lv0" in removed

    def test_removed_from_game_instead_of_discard(self, game):
        """本卡以移出游戏代替弃置（ROUND_ENDS 时从弃牌堆移出）。"""
        inv = game.state.get_investigator("player")
        game.action_resolver.perform_action(
            "player", Action.PLAY, card_id="eidetic_memory_lv3")
        # 出牌结算后进入弃牌堆（引擎无拦截钩子）
        assert "eidetic_memory_lv3" in inv.discard

        game.event_bus.emit(EventContext(
            game_state=game.state, event=GameEvent.ROUND_ENDS))
        assert "eidetic_memory_lv3" not in inv.discard
        removed = game.state.scenario.vars["removed_from_game"]
        assert "eidetic_memory_lv3" in removed

    def test_no_insight_event_in_discard(self, game):
        """弃牌堆无洞察事件：不复制任何效果，仅本卡被移出游戏。"""
        inv = game.state.get_investigator("player")
        inv.discard = []
        ok = game.action_resolver.perform_action(
            "player", Action.PLAY, card_id="eidetic_memory_lv3")
        assert ok is True
        assert inv.resources == 5  # 未支付复制费用
        assert "card_a" not in inv.hand

    def test_unaffordable_copy_not_chosen(self, game):
        """费用不可承担的洞察事件不会被自动选中。"""
        inv = game.state.get_investigator("player")
        inv.resources = 1  # 复制需2资源
        ok = game.action_resolver.perform_action(
            "player", Action.PLAY, card_id="eidetic_memory_lv3")
        assert ok is True
        assert inv.resources == 1
        assert "no_stone_unturned_lv0" in inv.discard  # 未被移出
