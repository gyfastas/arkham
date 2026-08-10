"""Tests for Geared Up (Level 0). (08019)

强制 - 游戏第一个回合开始时：从手牌减费打出任意数量物品支援；本回合-3行动。
"""

import pytest
from backend.cards.guardian.geared_up_lv0 import GearedUp
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import GameEvent, PlayerClass, SlotType
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_asset_data, make_event_data, make_investigator_data,
    make_location_data, make_skill_data,
)


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)
    inv_data = make_investigator_data()
    g.register_card_data(inv_data)
    g.register_card_data(make_location_data())
    g.register_card_data(make_asset_data(
        id="geared_up_lv0", name="Geared Up", cost=None,
        card_class=PlayerClass.GUARDIAN, traits=["talent"],
    ))
    g.register_card_data(make_asset_data(
        id="item_a", name="Item A", cost=2, card_class=PlayerClass.GUARDIAN,
        traits=["item"], slots=[SlotType.HAND]))
    g.register_card_data(make_asset_data(
        id="item_b", name="Item B", cost=3, card_class=PlayerClass.GUARDIAN,
        traits=["item", "tool"]))
    g.register_card_data(make_skill_data(id="skill_c", name="Skill C"))

    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", g.state.get_card_data("test_location"), clues=0)
    g.card_registry.register_class(GearedUp)

    inv = g.state.get_investigator("inv1")
    inst = CardInstance(
        instance_id="geared_1", card_id="geared_up_lv0",
        owner_id="inv1", controller_id="inv1",
    )
    g.state.cards_in_play["geared_1"] = inst
    inv.play_area.append("geared_1")
    g.card_registry.activate_card("geared_up_lv0", "geared_1", g.event_bus)
    return g


def _turn_begins(game):
    inv = game.state.get_investigator("inv1")
    inv.actions_remaining = 3  # 引擎在回合开始时重置
    ctx = EventContext(
        game_state=game.state, event=GameEvent.INVESTIGATOR_TURN_BEGINS,
        investigator_id="inv1",
    )
    game.event_bus.emit(ctx)
    return ctx


class TestGearedUp:
    def test_first_turn_plays_items_at_discount(self, game):
        """第一回合：物品各减1费打出，非物品留手，行动-3。"""
        inv = game.state.get_investigator("inv1")
        inv.hand = ["item_a", "item_b", "skill_c"]
        inv.resources = 3  # item_a:1 + item_b:2 = 3 → 恰好付得起

        ctx = _turn_begins(game)

        assert set(ctx.extra["geared_up_played"]) == {"item_a", "item_b"}
        assert inv.resources == 0
        assert inv.hand == ["skill_c"]  # 非物品不打出
        played_ids = [
            game.state.get_card_instance(iid).card_id for iid in inv.play_area
        ]
        assert "item_a" in played_ids and "item_b" in played_ids
        assert inv.actions_remaining == 0  # 3-3

    def test_not_triggered_after_round_1(self, game):
        """第二轮起不再触发。"""
        inv = game.state.get_investigator("inv1")
        inv.hand = ["item_a"]
        game.state.scenario.round_number = 2

        ctx = _turn_begins(game)
        assert "geared_up_played" not in ctx.extra
        assert inv.hand == ["item_a"]
        assert inv.actions_remaining == 3

    def test_unaffordable_items_stay(self, game):
        """减费后仍付不起的物品留在手牌。"""
        inv = game.state.get_investigator("inv1")
        inv.hand = ["item_b"]  # 3费→2费
        inv.resources = 1

        ctx = _turn_begins(game)
        assert ctx.extra["geared_up_played"] == []
        assert inv.hand == ["item_b"]
        assert inv.actions_remaining == 0
