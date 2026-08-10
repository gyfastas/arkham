"""Tests for Solemn Vow, Something Worth Fighting For, Spiritual Resolve.

庄严立誓(06020)：消耗转移1点伤害/恐惧给所有者控制的卡。
赴汤蹈火(05109)：同地点其他调查员的恐惧可由本卡承担。
摒绝杂念(06323)：弃手牌同名卡，治愈在场本卡全部伤害/恐惧。
"""

import pytest

from backend.cards.guardian.solemn_vow_lv0 import SolemnVow
from backend.cards.guardian.something_worth_fighting_for_lv0 import (
    SomethingWorthFightingFor,
)
from backend.cards.guardian.spiritual_resolve_lv5 import SpiritualResolve
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import (
    CardType, GameEvent, PlayerClass, SlotType,
)
from backend.models.state import CardData, CardInstance
from backend.tests.conftest import (
    make_asset_data, make_investigator_data, make_location_data,
)


def _game(two_invs=False):
    g = Game("test")
    g.chaos_bag.seed(42)
    inv_data = make_investigator_data()
    g.register_card_data(inv_data)
    loc = make_location_data()
    g.register_card_data(loc)
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", g.state.get_card_data("test_location"))
    if two_invs:
        g.add_investigator("inv2", inv_data, starting_location="test_location")
    return g


def _equip(game, card_id, impl_cls, iid="asset_1", owner="inv1",
           controller="inv1", health=None, sanity=None):
    game.register_card_data(make_asset_data(
        id=card_id, cost=0, health=health, sanity=sanity,
    ))
    game.card_registry.register_class(impl_cls)
    inst = CardInstance(
        instance_id=iid, card_id=card_id,
        owner_id=owner, controller_id=controller,
    )
    game.state.cards_in_play[iid] = inst
    game.state.get_investigator(controller).play_area.append(iid)
    return inst, game.card_registry.activate_card(
        card_id, iid, game.event_bus, chaos_bag=game.chaos_bag)


class TestSolemnVow:
    def test_transfer_damage_to_owner(self):
        """控制者消耗立誓：自己的1点伤害转移给所有者。"""
        game = _game(two_invs=True)
        inst, impl = _equip(
            game, "solemn_vow_lv0", SolemnVow, owner="inv1", controller="inv2",
        )
        inv1 = game.state.get_investigator("inv1")
        inv2 = game.state.get_investigator("inv2")
        inv2.damage = 2

        assert impl.activate_transfer(game.state, "inv2") is True
        assert inst.exhausted is True
        assert inv2.damage == 1
        assert inv1.damage == 1

    def test_transfer_horror(self):
        """可改为转移恐惧。"""
        game = _game(two_invs=True)
        _, impl = _equip(
            game, "solemn_vow_lv0", SolemnVow, owner="inv1", controller="inv2",
        )
        inv1 = game.state.get_investigator("inv1")
        inv2 = game.state.get_investigator("inv2")
        inv2.horror = 1

        assert impl.activate_transfer(game.state, "inv2", horror=True) is True
        assert inv2.horror == 0
        assert inv1.horror == 1

    def test_requires_owner_at_location(self):
        """所有者不在同地点：不能启动。"""
        game = _game(two_invs=True)
        other_loc = make_location_data(id="other_loc")
        game.register_card_data(other_loc)
        game.add_location("other_loc", other_loc)
        game.state.get_investigator("inv1").location_id = "other_loc"
        _, impl = _equip(
            game, "solemn_vow_lv0", SolemnVow, owner="inv1", controller="inv2",
        )
        game.state.get_investigator("inv2").damage = 1
        assert impl.activate_transfer(game.state, "inv2") is False


class TestSomethingWorthFightingFor:
    def test_soaks_horror_for_other_at_location(self):
        """同地点其他调查员被分配恐惧：由本卡承担。"""
        game = _game(two_invs=True)
        inst, _ = _equip(
            game, "something_worth_fighting_for_lv0",
            SomethingWorthFightingFor, sanity=3,
        )
        inv2 = game.state.get_investigator("inv2")

        ctx = EventContext(
            game_state=game.state, event=GameEvent.HORROR_ASSIGNED,
            investigator_id="inv2", amount=2,
        )
        game.event_bus.emit(ctx)
        assert ctx.amount == 0
        assert inst.horror == 2

    def test_no_soak_for_holder(self):
        """持有者自己被分配恐惧：不触发。"""
        game = _game()
        inst, _ = _equip(
            game, "something_worth_fighting_for_lv0",
            SomethingWorthFightingFor, sanity=3,
        )
        ctx = EventContext(
            game_state=game.state, event=GameEvent.HORROR_ASSIGNED,
            investigator_id="inv1", amount=2,
        )
        game.event_bus.emit(ctx)
        assert ctx.amount == 2
        assert inst.horror == 0

    def test_defeated_at_sanity_limit(self):
        """承恐达到理智上限：被击败离场。"""
        game = _game(two_invs=True)
        inst, _ = _equip(
            game, "something_worth_fighting_for_lv0",
            SomethingWorthFightingFor, sanity=3,
        )
        ctx = EventContext(
            game_state=game.state, event=GameEvent.HORROR_ASSIGNED,
            investigator_id="inv2", amount=5,
        )
        game.event_bus.emit(ctx)
        assert ctx.amount == 2  # 只承担3点
        inv1 = game.state.get_investigator("inv1")
        assert "asset_1" not in inv1.play_area


class TestSpiritualResolve:
    def test_heal_by_discarding_hand_copy(self):
        """弃手牌中一张同名卡：治愈在场本卡全部伤害/恐惧。"""
        game = _game()
        inst, impl = _equip(
            game, "spiritual_resolve_lv5", SpiritualResolve,
            health=3, sanity=3,
        )
        inv = game.state.get_investigator("inv1")
        inv.hand.append("spiritual_resolve_lv5")
        inst.damage = 2
        inst.horror = 1

        assert impl.activate_heal(game.state, "inv1") is True
        assert inst.damage == 0 and inst.horror == 0
        assert "spiritual_resolve_lv5" not in inv.hand
        assert "spiritual_resolve_lv5" in inv.discard

    def test_requires_hand_copy(self):
        """手牌没有同名卡：不能启动。"""
        game = _game()
        inst, impl = _equip(
            game, "spiritual_resolve_lv5", SpiritualResolve,
            health=3, sanity=3,
        )
        inst.damage = 1
        assert impl.activate_heal(game.state, "inv1") is False
        assert inst.damage == 1
