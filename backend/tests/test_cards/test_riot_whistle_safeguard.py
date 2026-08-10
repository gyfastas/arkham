"""Tests for Riot Whistle (Level 0) and Safeguard (Level 2). (07108/06196)

警哨：你的回合中有一个额外行动（限交战，会话层校验）。
安全护卫：他人回合消耗后，跟随其从你地点移向连接地点。
"""

import pytest

from backend.cards.guardian.riot_whistle_lv0 import RiotWhistle
from backend.cards.guardian.safeguard_lv2 import Safeguard
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import (
    CardType, GameEvent, PlayerClass,
)
from backend.models.state import CardData, CardInstance
from backend.tests.conftest import (
    make_asset_data, make_investigator_data, make_location_data,
)


def _game(two_invs=False, two_locs=False):
    g = Game("test")
    g.chaos_bag.seed(42)
    inv_data = make_investigator_data()
    g.register_card_data(inv_data)
    if two_locs:
        loc_a = make_location_data(id="loc_a", connections=["loc_b"])
        loc_b = make_location_data(id="loc_b", connections=["loc_a"])
        g.register_card_data(loc_a)
        g.register_card_data(loc_b)
        g.add_location("loc_a", loc_a)
        g.add_location("loc_b", loc_b)
        start = "loc_a"
    else:
        loc = make_location_data()
        g.register_card_data(loc)
        g.add_location("test_location", loc)
        start = "test_location"
    g.add_investigator("inv1", inv_data, starting_location=start)
    if two_invs:
        g.add_investigator("inv2", inv_data, starting_location=start)
    return g


def _equip(game, card_id, impl_cls, iid="asset_1"):
    game.register_card_data(make_asset_data(id=card_id, cost=2))
    game.card_registry.register_class(impl_cls)
    inst = CardInstance(
        instance_id=iid, card_id=card_id,
        owner_id="inv1", controller_id="inv1",
    )
    game.state.cards_in_play[iid] = inst
    game.state.get_investigator("inv1").play_area.append(iid)
    return inst, game.card_registry.activate_card(
        card_id, iid, game.event_bus, chaos_bag=game.chaos_bag)


class TestRiotWhistle:
    def test_extra_action_on_turn_begins(self):
        """装备者回合开始：3行动+1=4。"""
        game = _game()
        _equip(game, "riot_whistle_lv0", RiotWhistle)
        inv = game.state.get_investigator("inv1")
        inv.actions_remaining = 3

        game.event_bus.emit(EventContext(
            game_state=game.state, event=GameEvent.INVESTIGATOR_TURN_BEGINS,
            investigator_id="inv1",
        ))
        assert inv.actions_remaining == 4

    def test_no_action_for_other_investigator(self):
        """其他调查员回合开始：不加行动。"""
        game = _game(two_invs=True)
        _equip(game, "riot_whistle_lv0", RiotWhistle)
        inv2 = game.state.get_investigator("inv2")
        inv2.actions_remaining = 3

        game.event_bus.emit(EventContext(
            game_state=game.state, event=GameEvent.INVESTIGATOR_TURN_BEGINS,
            investigator_id="inv2",
        ))
        assert inv2.actions_remaining == 3


class TestSafeguard:
    def test_follow_move(self):
        """武装后：另一位调查员从你地点移向连接地点时跟随移动。"""
        game = _game(two_invs=True, two_locs=True)
        inst, impl = _equip(game, "safeguard_lv2", Safeguard)
        inv1 = game.state.get_investigator("inv1")

        assert impl.activate(game.state, "inv1") is True
        assert inst.exhausted is True

        # 引擎在移动生效前发出事件（inv2 仍在 loc_a）
        game.event_bus.emit(EventContext(
            game_state=game.state, event=GameEvent.MOVE_ACTION_INITIATED,
            investigator_id="inv2", location_id="loc_b",
        ))
        assert inv1.location_id == "loc_b"

    def test_no_follow_without_activate(self):
        """未启动：不跟随。"""
        game = _game(two_invs=True, two_locs=True)
        _equip(game, "safeguard_lv2", Safeguard)
        inv1 = game.state.get_investigator("inv1")

        game.event_bus.emit(EventContext(
            game_state=game.state, event=GameEvent.MOVE_ACTION_INITIATED,
            investigator_id="inv2", location_id="loc_b",
        ))
        assert inv1.location_id == "loc_a"

    def test_disarm_at_turn_end(self):
        """回合结束解除武装：下一回合的移动不再跟随。"""
        game = _game(two_invs=True, two_locs=True)
        _, impl = _equip(game, "safeguard_lv2", Safeguard)
        inv1 = game.state.get_investigator("inv1")
        impl.activate(game.state, "inv1")

        game.event_bus.emit(EventContext(
            game_state=game.state, event=GameEvent.INVESTIGATOR_TURN_ENDS,
            investigator_id="inv2",
        ))
        # inv2 回到同地点再移动：不再跟随
        game.event_bus.emit(EventContext(
            game_state=game.state, event=GameEvent.MOVE_ACTION_INITIATED,
            investigator_id="inv2", location_id="loc_b",
        ))
        assert inv1.location_id == "loc_a"
