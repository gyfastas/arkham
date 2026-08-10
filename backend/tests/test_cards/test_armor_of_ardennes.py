"""Tests for Armor of Ardennes (Level 5). (03305)

[反应]当伤害被分配给阿登护甲时，横置它：取消其中1点伤害。
"""

import pytest
from backend.cards.guardian.armor_of_ardennes_lv5 import ArmorOfArdennes
from backend.engine.game import Game
from backend.models.enums import CardType, PlayerClass, SlotType
from backend.models.state import CardData, CardInstance
from backend.tests.conftest import (
    make_investigator_data, make_location_data,
)


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)

    inv_data = make_investigator_data()
    g.register_card_data(inv_data)
    g.register_card_data(make_location_data())
    g.register_card_data(CardData(
        id="armor_of_ardennes_lv5", name="Armor of Ardennes", name_cn="阿登护甲",
        type=CardType.ASSET, card_class=PlayerClass.GUARDIAN, cost=4,
        slots=[SlotType.BODY], traits=["item", "armor", "relic"], health=4,
    ))

    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", g.state.get_card_data("test_location"), clues=2)
    g.card_registry.register_class(ArmorOfArdennes)

    inv = g.state.get_investigator("inv1")
    inst = CardInstance(
        instance_id="armor_1", card_id="armor_of_ardennes_lv5",
        owner_id="inv1", controller_id="inv1", slot_used=[SlotType.BODY],
    )
    g.state.cards_in_play["armor_1"] = inst
    inv.play_area.append("armor_1")
    g.card_registry.activate_card("armor_of_ardennes_lv5", "armor_1", g.event_bus)
    return g


class TestArmorOfArdennes:
    def test_exhausts_to_cancel_1_assigned_damage(self, game):
        """2点伤害分配给护甲：横置并取消1点，护甲只受1点。"""
        inst = game.state.get_card_instance("armor_1")
        inv = game.state.get_investigator("inv1")

        game.damage_engine.deal_damage(
            "inv1", damage=2, damage_assignment={"armor_1": 2},
        )
        assert inst.exhausted is True
        assert inst.damage == 1  # 2 - 取消1
        assert inv.damage == 0

    def test_no_cancel_while_exhausted(self, game):
        """已横置时不再取消。"""
        inst = game.state.get_card_instance("armor_1")
        inst.exhausted = True

        game.damage_engine.deal_damage(
            "inv1", damage=2, damage_assignment={"armor_1": 2},
        )
        assert inst.damage == 2

    def test_no_trigger_without_assignment(self, game):
        """伤害全部分给调查员（未分给护甲）时不触发。"""
        inst = game.state.get_card_instance("armor_1")
        inv = game.state.get_investigator("inv1")

        game.damage_engine.deal_damage("inv1", damage=2)
        assert inst.exhausted is False
        assert inst.damage == 0
        assert inv.damage == 2
