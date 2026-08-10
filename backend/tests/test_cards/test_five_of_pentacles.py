"""Tests for Five of Pentacles (Level 1)."""

import pytest

from backend.cards.survivor.five_of_pentacles_lv1 import FiveOfPentacles
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import Action, GameEvent, SlotType
from backend.tests.conftest import (
    make_asset_data, make_investigator_data, make_location_data,
)


@pytest.fixture
def game():
    g = Game("test")
    inv_data = make_investigator_data(health=7, sanity=7)
    g.register_card_data(inv_data)
    loc = make_location_data()
    g.register_card_data(loc)
    g.register_card_data(make_asset_data(
        id="five_of_pentacles_lv1", name="Five of Pentacles", cost=3,
        slots=[SlotType.TAROT], traits=["tarot"]))
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)
    g.card_registry.register_class(FiveOfPentacles)
    return g


class TestFiveOfPentacles:
    def test_card_registered(self, game):
        assert "five_of_pentacles_lv1" in game.card_registry.registered_cards

    def test_normal_play_grants_health_and_sanity(self, game):
        """正常打出：+1生命值、+1神智值。"""
        inv = game.state.get_investigator("inv1")
        inv.resources = 5
        inv.hand = ["five_of_pentacles_lv1"]
        assert game.action_resolver.perform_action(
            "inv1", Action.PLAY, card_id="five_of_pentacles_lv1") is True
        assert inv.health == 8
        assert inv.sanity == 8
        assert inv.health_bonus == 1
        assert inv.sanity_bonus == 1

    def test_opening_hand_put_into_play(self, game):
        """游戏开始时在起始手牌中：自动放置入场并获得+1/+1。"""
        inv = game.state.get_investigator("inv1")
        inv.hand = ["five_of_pentacles_lv1"]
        # game 初始即 SETUP 阶段
        from backend.models.enums import Phase
        assert game.state.scenario.current_phase == Phase.SETUP
        impl = FiveOfPentacles("impl_fop")
        impl.register(game.event_bus, "impl_fop")

        game.event_bus.emit(EventContext(
            game_state=game.state, event=GameEvent.CARD_DRAWN,
            investigator_id="inv1",
            extra={"card_id": "five_of_pentacles_lv1"}))

        assert "five_of_pentacles_lv1" not in inv.hand
        iids = [i for i in inv.play_area
                if game.state.get_card_instance(i).card_id
                == "five_of_pentacles_lv1"]
        assert len(iids) == 1
        assert inv.health == 8
        assert inv.sanity == 8
        # 占用塔罗槽
        mgr = game.slot_managers["inv1"]
        assert mgr.slots[SlotType.TAROT] == iids

    def test_leaves_play_removes_bonus(self, game):
        """离场：移除+1/+1。"""
        inv = game.state.get_investigator("inv1")
        inv.resources = 5
        inv.hand = ["five_of_pentacles_lv1"]
        game.action_resolver.perform_action(
            "inv1", Action.PLAY, card_id="five_of_pentacles_lv1")
        iid = next(i for i in inv.play_area
                   if game.state.get_card_instance(i).card_id
                   == "five_of_pentacles_lv1")
        assert inv.health == 8

        # 模拟被击败离场（走引擎的移除通道，发 CARD_LEAVES_PLAY）
        game.damage_engine._remove_card_from_play(iid)
        assert inv.health == 7
        assert inv.sanity == 7
