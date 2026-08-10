"""Tests for Bob Jenkins investigator ability."""

import pytest
from backend.cards.survivor.bob_jenkins import BobJenkins
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import ChaosTokenType, GameEvent, SlotType
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_asset_data, make_investigator_data, make_location_data,
)


@pytest.fixture
def game():
    g = Game("test_bob")
    g.chaos_bag.seed(42)

    bob_data = make_investigator_data(id="bob_jenkins", name="Bob Jenkins")
    g.register_card_data(bob_data)
    other_data = make_investigator_data(id="other_inv", name="Other")
    g.register_card_data(other_data)

    loc_data = make_location_data()
    g.register_card_data(loc_data)
    far_loc = make_location_data(id="far_location")
    g.register_card_data(far_loc)

    g.register_card_data(make_asset_data(
        id="item_flashlight", name="Flashlight", cost=2,
        slots=[SlotType.HAND], traits=["item", "tool"]))
    g.register_card_data(make_asset_data(
        id="item_liquor", name="Liquor", cost=1, traits=["item"]))
    g.register_card_data(make_asset_data(
        id="tome_asset", name="Tome", cost=2,
        slots=[SlotType.HAND], traits=["tome"]))

    deck = ["card_a", "card_b", "card_c", "card_d", "card_e"] * 3
    g.add_investigator("bob", bob_data, deck=deck, starting_location="test_location")
    g.add_investigator("other", other_data, deck=list(deck),
                       starting_location="test_location")
    g.add_location("test_location", loc_data, clues=3)
    g.add_location("far_location", far_loc, clues=0)

    return g


@pytest.fixture
def impl(game):
    impl = BobJenkins("test_instance")
    impl.register(game.event_bus, "test_instance")
    return impl


def _emit(game, event, **kwargs):
    ctx = EventContext(game_state=game.state, event=event, **kwargs)
    game.event_bus.emit(ctx)
    return ctx


def _put_in_play(game, inv, card_id, instance_id):
    inst = CardInstance(
        instance_id=instance_id, card_id=card_id,
        owner_id=inv.investigator_id, controller_id=inv.investigator_id,
    )
    game.state.cards_in_play[instance_id] = inst
    inv.play_area.append(instance_id)
    return inst


class TestBobPlayItem:
    def test_play_item_from_other_hand_under_their_control(self, game, impl):
        """额外行动：打出同地点调查员手中道具，置于其控制下；费用其全付。"""
        bob = game.state.get_investigator("bob")
        other = game.state.get_investigator("other")
        bob.resources = 3
        other.resources = 5
        other.hand = ["item_flashlight"]

        _emit(game, GameEvent.INVESTIGATOR_TURN_BEGINS, investigator_id="bob")
        assert impl.activate_play_item(
            game.state, "bob", "other", "item_flashlight") is True

        assert other.resources == 5 - 2  # 持有者付全款
        assert bob.resources == 3
        assert "item_flashlight" not in other.hand
        inst = game.state.cards_in_play[other.play_area[0]]
        assert inst.card_id == "item_flashlight"
        assert inst.controller_id == "other"
        # 占用持有者手槽
        slot_mgr = game.slot_managers["other"]
        assert slot_mgr.slots[SlotType.HAND] == [inst.instance_id]
        # 不消耗普通行动
        assert bob.actions_remaining == 3

    def test_item_action_once_per_turn(self, game, impl):
        """道具行动每回合1次；下回合重置。"""
        bob = game.state.get_investigator("bob")
        other = game.state.get_investigator("other")
        bob.resources = 10
        other.resources = 10
        other.hand = ["item_flashlight", "item_liquor"]

        _emit(game, GameEvent.INVESTIGATOR_TURN_BEGINS, investigator_id="bob")
        assert impl.activate_play_item(
            game.state, "bob", "other", "item_flashlight") is True
        assert impl.activate_play_item(
            game.state, "bob", "other", "item_liquor") is False

        _emit(game, GameEvent.INVESTIGATOR_TURN_ENDS, investigator_id="bob")
        _emit(game, GameEvent.INVESTIGATOR_TURN_BEGINS, investigator_id="bob")
        assert impl.activate_play_item(
            game.state, "bob", "other", "item_liquor") is True

    def test_not_available_outside_bobs_turn(self, game, impl):
        """非鲍勃回合不可用。"""
        other = game.state.get_investigator("other")
        other.resources = 5
        other.hand = ["item_flashlight"]
        assert impl.activate_play_item(
            game.state, "bob", "other", "item_flashlight") is False

    def test_rejects_non_item_and_other_location(self, game, impl):
        """非道具卡、不同地点调查员均不可。"""
        other = game.state.get_investigator("other")
        other.resources = 5
        other.hand = ["tome_asset"]
        _emit(game, GameEvent.INVESTIGATOR_TURN_BEGINS, investigator_id="bob")
        assert impl.activate_play_item(
            game.state, "bob", "other", "tome_asset") is False

        other.location_id = "far_location"
        other.hand = ["item_flashlight"]
        assert impl.activate_play_item(
            game.state, "bob", "other", "item_flashlight") is False

    def test_cost_split_bob_covers_remainder(self, game, impl):
        """持有者不足时鲍勃补余款；合计不足则失败。"""
        bob = game.state.get_investigator("bob")
        other = game.state.get_investigator("other")
        bob.resources = 2
        other.resources = 1  # item_flashlight 2费：持有者付1，鲍勃付1
        other.hand = ["item_flashlight"]

        _emit(game, GameEvent.INVESTIGATOR_TURN_BEGINS, investigator_id="bob")
        assert impl.activate_play_item(
            game.state, "bob", "other", "item_flashlight") is True
        assert other.resources == 0
        assert bob.resources == 1

    def test_explicit_bob_pays(self, game, impl):
        """显式指定鲍勃出资额。"""
        bob = game.state.get_investigator("bob")
        other = game.state.get_investigator("other")
        bob.resources = 5
        other.resources = 5
        other.hand = ["item_flashlight"]

        _emit(game, GameEvent.INVESTIGATOR_TURN_BEGINS, investigator_id="bob")
        assert impl.activate_play_item(
            game.state, "bob", "other", "item_flashlight", bob_pays=2) is True
        assert bob.resources == 3
        assert other.resources == 5


class TestBobElderSign:
    def test_elder_sign_plus_per_item(self, game, impl):
        """远古印记：每控制1张道具支援 +1。"""
        bob = game.state.get_investigator("bob")
        _put_in_play(game, bob, "item_flashlight", "inst_1")
        _put_in_play(game, bob, "item_liquor", "inst_2")
        _put_in_play(game, bob, "tome_asset", "inst_3")  # 非道具不计

        ctx = _emit(
            game, GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="bob", chaos_token=ChaosTokenType.ELDER_SIGN,
        )
        assert ctx.amount == 2

    def test_elder_sign_counts_only_bobs_items(self, game, impl):
        """他人控制的道具不计入。"""
        other = game.state.get_investigator("other")
        _put_in_play(game, other, "item_flashlight", "inst_1")

        ctx = _emit(
            game, GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="bob", chaos_token=ChaosTokenType.ELDER_SIGN,
        )
        assert ctx.amount == 0

    def test_non_elder_sign_no_bonus(self, game, impl):
        bob = game.state.get_investigator("bob")
        _put_in_play(game, bob, "item_flashlight", "inst_1")
        ctx = _emit(
            game, GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="bob", chaos_token=ChaosTokenType.SKULL, amount=-2,
        )
        assert ctx.amount == -2
