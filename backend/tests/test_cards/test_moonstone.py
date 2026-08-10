"""Tests for Moonstone (Level 0)."""

import pytest
from backend.cards.survivor.moonstone_lv0 import Moonstone
from backend.models.enums import ChaosTokenType, PlayerClass, Skill, SlotType
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_asset_data, make_investigator_data, make_location_data,
)
from backend.engine.game import Game


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)
    inv_data = make_investigator_data(willpower=3, agility=3)
    g.register_card_data(inv_data)
    loc = make_location_data()
    g.register_card_data(loc)
    g.register_card_data(make_asset_data(
        id="moonstone_lv0", name="Moonstone", cost=3,
        card_class=PlayerClass.SURVIVOR, slots=[SlotType.ACCESSORY],
        traits=["item", "relic", "dreamlands"],
    ))
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)
    g.card_registry.register_class(Moonstone)
    return g


class TestMoonstone:
    def test_card_registered(self, game):
        assert "moonstone_lv0" in game.card_registry.registered_cards

    def test_passive_bonus_in_play(self, game):
        """在场时 +1 意志、+1 敏捷。"""
        inv = game.state.get_investigator("inv1")
        iid = game.state.next_instance_id()
        game.state.cards_in_play[iid] = CardInstance(
            instance_id=iid, card_id="moonstone_lv0",
            owner_id="inv1", controller_id="inv1",
            slot_used=[SlotType.ACCESSORY],
        )
        inv.play_area.append(iid)
        game.card_registry.activate_card("moonstone_lv0", iid, game.event_bus)

        game.chaos_bag.tokens = [ChaosTokenType.ZERO]
        r1 = game.skill_test_engine.run_test("inv1", Skill.WILLPOWER, 4)
        assert r1.modified_skill == 4
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]
        r2 = game.skill_test_engine.run_test("inv1", Skill.AGILITY, 4)
        assert r2.modified_skill == 4

    def test_discard_and_play_from_hand(self, game):
        """从手牌弃置后：支付费用打出（占饰品槽，不进弃牌堆）。"""
        inv = game.state.get_investigator("inv1")
        inv.hand = ["moonstone_lv0"]
        inv.resources = 5
        impl = Moonstone("impl_moonstone")
        impl.register(game.event_bus, "impl_moonstone")

        assert impl.discard_and_play(game.state, "inv1") is True

        assert inv.resources == 2
        assert "moonstone_lv0" not in inv.hand
        assert "moonstone_lv0" not in inv.discard
        new_iid = inv.play_area[-1]
        inst = game.state.get_card_instance(new_iid)
        assert inst.card_id == "moonstone_lv0"
        assert inst.slot_used == [SlotType.ACCESSORY]

    def test_discard_and_play_requires_resources(self, game):
        inv = game.state.get_investigator("inv1")
        inv.hand = ["moonstone_lv0"]
        inv.resources = 2
        impl = Moonstone("impl_moonstone2")
        impl.register(game.event_bus, "impl_moonstone2")

        assert impl.discard_and_play(game.state, "inv1") is False
        assert "moonstone_lv0" in inv.hand
