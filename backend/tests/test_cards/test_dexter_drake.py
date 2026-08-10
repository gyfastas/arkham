"""Tests for Dexter Drake investigator ability."""

import pytest
from backend.cards.mystic.dexter_drake import DexterDrake
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import ChaosTokenType, GameEvent, SlotType
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_asset_data, make_investigator_data, make_location_data,
)


@pytest.fixture
def game():
    g = Game("test_dexter")
    g.chaos_bag.seed(42)

    inv_data = make_investigator_data(id="dexter_drake", name="Dexter Drake")
    g.register_card_data(inv_data)

    loc_data = make_location_data()
    g.register_card_data(loc_data)

    g.register_card_data(make_asset_data(
        id="old_asset", name="Old Asset", cost=1, slots=[SlotType.ARCANE]))
    g.register_card_data(make_asset_data(
        id="new_asset", name="New Asset", cost=3, slots=[SlotType.ARCANE]))
    g.register_card_data(make_asset_data(
        id="new_asset_copy", name="New Asset", cost=2))  # 同名卡
    g.register_card_data(make_asset_data(
        id="expensive_asset", name="Expensive Asset", cost=6))

    deck = ["card_a", "card_b", "card_c", "card_d", "card_e"] * 3
    g.add_investigator("dexter", inv_data, deck=deck, starting_location="test_location")
    g.add_location("test_location", loc_data, clues=3)

    return g


@pytest.fixture
def impl(game):
    impl = DexterDrake("test_instance")
    impl.register(game.event_bus, "test_instance")
    return impl


def _emit(game, event, **kwargs):
    ctx = EventContext(game_state=game.state, event=event, **kwargs)
    game.event_bus.emit(ctx)
    return ctx


def _put_in_play(game, inv, card_id, instance_id="asset_1"):
    inst = CardInstance(
        instance_id=instance_id, card_id=card_id,
        owner_id=inv.investigator_id, controller_id=inv.investigator_id,
        slot_used=list(game.state.get_card_data(card_id).slots or []),
    )
    game.state.cards_in_play[instance_id] = inst
    inv.play_area.append(instance_id)
    slot_mgr = game.slot_managers[inv.investigator_id]
    cd = game.state.get_card_data(card_id)
    if cd.slots:
        slot_mgr.occupy(instance_id, cd.slots, cd.traits)
    return inst


class TestDexterSwap:
    def test_swap_plays_asset_at_reduced_cost(self, game, impl):
        """弃1支援打出不同名支援：费用-1、旧支援入弃牌堆、槽位交接。"""
        inv = game.state.get_investigator("dexter")
        inv.resources = 5
        _put_in_play(game, inv, "old_asset", "asset_1")
        inv.hand = ["new_asset", "card_a"]

        _emit(game, GameEvent.INVESTIGATOR_TURN_BEGINS, investigator_id="dexter")
        assert impl.activate_swap(game.state, "dexter", "asset_1", "new_asset") is True

        assert inv.resources == 5 - 2  # 3费-1
        assert "old_asset" in inv.discard
        assert "asset_1" not in inv.play_area
        assert "new_asset" not in inv.hand
        new_inst = [game.state.cards_in_play[i] for i in inv.play_area][0]
        assert new_inst.card_id == "new_asset"
        # 槽位：旧支援的奥秘槽已释放，新支援占用
        slot_mgr = game.slot_managers["dexter"]
        assert slot_mgr.slots[SlotType.ARCANE] == [new_inst.instance_id]

    def test_swap_once_per_round(self, game, impl):
        """每轮限1次；新一轮重置。"""
        inv = game.state.get_investigator("dexter")
        inv.resources = 10
        _put_in_play(game, inv, "old_asset", "asset_1")
        inv.hand = ["new_asset", "expensive_asset"]

        _emit(game, GameEvent.INVESTIGATOR_TURN_BEGINS, investigator_id="dexter")
        assert impl.activate_swap(game.state, "dexter", "asset_1", "new_asset") is True
        assert impl.activate_swap(
            game.state, "dexter", "asset_1", "expensive_asset") is False

        _emit(game, GameEvent.INVESTIGATOR_TURN_ENDS, investigator_id="dexter")
        _emit(game, GameEvent.ROUND_BEGINS)
        _emit(game, GameEvent.INVESTIGATOR_TURN_BEGINS, investigator_id="dexter")
        new_inst_id = inv.play_area[0]
        assert impl.activate_swap(
            game.state, "dexter", new_inst_id, "expensive_asset") is True

    def test_swap_only_during_own_turn(self, game, impl):
        """非自己回合不能发动。"""
        inv = game.state.get_investigator("dexter")
        inv.resources = 5
        _put_in_play(game, inv, "old_asset", "asset_1")
        inv.hand = ["new_asset"]

        assert impl.activate_swap(game.state, "dexter", "asset_1", "new_asset") is False

    def test_swap_rejects_same_title(self, game, impl):
        """不能打出同名（同 title）支援。"""
        inv = game.state.get_investigator("dexter")
        inv.resources = 5
        _put_in_play(game, inv, "new_asset", "asset_1")
        inv.hand = ["new_asset_copy"]

        _emit(game, GameEvent.INVESTIGATOR_TURN_BEGINS, investigator_id="dexter")
        assert impl.activate_swap(
            game.state, "dexter", "asset_1", "new_asset_copy") is False

    def test_swap_rejects_unaffordable(self, game, impl):
        """减1费后仍付不起则不能发动。"""
        inv = game.state.get_investigator("dexter")
        inv.resources = 4  # expensive_asset 6费-1=5
        _put_in_play(game, inv, "old_asset", "asset_1")
        inv.hand = ["expensive_asset"]

        _emit(game, GameEvent.INVESTIGATOR_TURN_BEGINS, investigator_id="dexter")
        assert impl.activate_swap(
            game.state, "dexter", "asset_1", "expensive_asset") is False


class TestDexterElderSign:
    def test_elder_sign_plus_two_only_without_preset(self, game, impl):
        """远古印记：无预设时仅 +2，不抽牌。"""
        inv = game.state.get_investigator("dexter")
        hand_before = len(inv.hand)
        ctx = _emit(
            game, GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="dexter", chaos_token=ChaosTokenType.ELDER_SIGN,
        )
        assert ctx.amount == 2
        assert len(inv.hand) == hand_before

    def test_elder_sign_return_asset_and_draw(self, game, impl):
        """预设返回在场支援：+2、支援回手、然后抽1张牌。"""
        inv = game.state.get_investigator("dexter")
        _put_in_play(game, inv, "old_asset", "asset_1")
        hand_before = len(inv.hand)
        deck_before = len(inv.deck)

        assert impl.choose_elder_sign_return(game.state, "dexter", "asset_1") is True
        ctx = _emit(
            game, GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="dexter", chaos_token=ChaosTokenType.ELDER_SIGN,
        )
        assert ctx.amount == 2
        assert "asset_1" not in inv.play_area
        assert "old_asset" in inv.hand
        # 抽1张：返回的支援 + 牌库顶
        assert len(inv.hand) == hand_before + 2
        assert len(inv.deck) == deck_before - 1
        # 预设已消费
        assert "dexter_elder_sign_return" not in game.state.scenario.vars

    def test_choose_return_validates_play_area(self, game, impl):
        """预设目标必须在场。"""
        assert impl.choose_elder_sign_return(
            game.state, "dexter", "nonexistent") is False
