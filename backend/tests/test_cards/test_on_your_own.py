"""Tests for On Your Own (Level 3)."""

import pytest
from backend.cards.survivor.on_your_own_lv3 import OnYourOwn
from backend.models.enums import (
    Action, GameEvent, PlayerClass, SlotType,
)
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_asset_data, make_event_data, make_investigator_data,
    make_location_data,
)
from backend.engine.event_bus import EventContext
from backend.engine.game import Game


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)
    inv_data = make_investigator_data()
    g.register_card_data(inv_data)
    loc = make_location_data()
    g.register_card_data(loc)
    g.register_card_data(make_asset_data(
        id="on_your_own_lv3", name="On Your Own", cost=2,
        card_class=PlayerClass.SURVIVOR, traits=["talent"]))
    g.register_card_data(make_event_data(
        id="survivor_event", name="Survivor Event", cost=2,
        card_class=PlayerClass.SURVIVOR))
    g.register_card_data(make_event_data(
        id="guardian_event", name="Guardian Event", cost=2,
        card_class=PlayerClass.GUARDIAN))
    g.register_card_data(make_asset_data(
        id="ally_asset", name="Ally", slots=[SlotType.ALLY],
        traits=["ally"]))
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)
    g.card_registry.register_class(OnYourOwn)
    return g


def _equip_oyo(game):
    inv = game.state.get_investigator("inv1")
    iid = game.state.next_instance_id()
    game.state.cards_in_play[iid] = CardInstance(
        instance_id=iid, card_id="on_your_own_lv3",
        owner_id="inv1", controller_id="inv1",
    )
    inv.play_area.append(iid)
    game.card_registry.activate_card("on_your_own_lv3", iid, game.event_bus)
    return iid


class TestOnYourOwn:
    def test_card_registered(self, game):
        assert "on_your_own_lv3" in game.card_registry.registered_cards

    def test_survivor_event_cost_refund(self, game):
        """打出求生者事件：横置并返还至多2资源。"""
        oyo_id = _equip_oyo(game)
        inv = game.state.get_investigator("inv1")
        inv.hand = ["survivor_event"]
        inv.resources = 5

        assert game.action_resolver.perform_action(
            "inv1", Action.PLAY, card_id="survivor_event") is True

        assert inv.resources == 5  # 5 - 2 + 2返还
        assert game.state.get_card_instance(oyo_id).exhausted is True

    def test_no_discount_for_other_class(self, game):
        """非求生者事件不触发。"""
        oyo_id = _equip_oyo(game)
        inv = game.state.get_investigator("inv1")
        inv.hand = ["guardian_event"]
        inv.resources = 5

        game.action_resolver.perform_action(
            "inv1", Action.PLAY, card_id="guardian_event")

        assert inv.resources == 3  # 仅支付2费
        assert game.state.get_card_instance(oyo_id).exhausted is False

    def test_discarded_when_ally_enters(self, game):
        """控制盟友槽支援时弃置孤身一人。"""
        oyo_id = _equip_oyo(game)
        inv = game.state.get_investigator("inv1")
        ally_id = game.state.next_instance_id()
        game.state.cards_in_play[ally_id] = CardInstance(
            instance_id=ally_id, card_id="ally_asset",
            owner_id="inv1", controller_id="inv1", slot_used=[SlotType.ALLY],
        )
        inv.play_area.append(ally_id)

        game.event_bus.emit(EventContext(
            game_state=game.state, event=GameEvent.CARD_ENTERS_PLAY,
            investigator_id="inv1", target=ally_id,
            extra={"card_id": "ally_asset"},
        ))

        assert oyo_id not in inv.play_area
        assert "on_your_own_lv3" in inv.discard
