"""Tests for First Aid (Level 3)."""

import pytest
from backend.cards.guardian.first_aid_lv3 import FirstAidLv3
from backend.models.enums import SlotType
from backend.models.state import CardInstance
from backend.tests.conftest import make_asset_data


@pytest.fixture
def aid_game(game):
    game.register_card_data(make_asset_data(
        id="first_aid_lv3", name="First Aid", traits=["talent", "science"],
        uses={"supplies": 4},
    ))
    inv = game.state.get_investigator("test_investigator")
    inst = CardInstance(
        instance_id="aid_1", card_id="first_aid_lv3",
        owner_id="test_investigator", controller_id="test_investigator",
        uses={"supplies": 4},
    )
    game.state.cards_in_play["aid_1"] = inst
    inv.play_area.append("aid_1")

    game.card_registry.register_class(FirstAidLv3)
    game.card_registry.activate_card("first_aid_lv3", "aid_1", game.event_bus)
    return game


class TestFirstAidLv3:
    def test_card_id(self):
        assert FirstAidLv3.card_id == "first_aid_lv3"

    def test_heals_1_damage_and_1_horror(self, aid_game):
        """花1补给同时治愈1点伤害和1点恐惧。"""
        game = aid_game
        inv = game.state.get_investigator("test_investigator")
        inv.damage = 2
        inv.horror = 1

        impl = game.card_registry.active_instances.get("aid_1")
        assert impl.activate(game.state, "test_investigator") is True
        assert inv.damage == 1
        assert inv.horror == 0
        inst = game.state.get_card_instance("aid_1")
        assert inst.uses["supplies"] == 3

    def test_heals_ally_at_location(self, aid_game):
        """可治愈同地点调查员控制的盟友。"""
        game = aid_game
        game.register_card_data(make_asset_data(
            id="guard_dog_lv0", name="Guard Dog",
            slots=[SlotType.ALLY], traits=["ally", "creature"],
            health=3, sanity=1,
        ))
        inv = game.state.get_investigator("test_investigator")
        dog = CardInstance(
            instance_id="dog_1", card_id="guard_dog_lv0",
            owner_id="test_investigator", controller_id="test_investigator",
        )
        dog.damage = 1
        dog.horror = 1
        game.state.cards_in_play["dog_1"] = dog
        inv.play_area.append("dog_1")

        impl = game.card_registry.active_instances.get("aid_1")
        assert impl.activate(game.state, "test_investigator",
                             target_instance_id="dog_1") is True
        assert dog.damage == 0
        assert dog.horror == 0

    def test_partial_heal_ok(self, aid_game):
        """目标只有伤害（无恐惧）也可启动。"""
        game = aid_game
        inv = game.state.get_investigator("test_investigator")
        inv.damage = 1

        impl = game.card_registry.active_instances.get("aid_1")
        assert impl.activate(game.state, "test_investigator") is True
        assert inv.damage == 0

    def test_discard_when_supplies_exhausted(self, aid_game):
        """补给耗尽后弃置急救。"""
        game = aid_game
        inv = game.state.get_investigator("test_investigator")
        inst = game.state.get_card_instance("aid_1")
        inst.uses["supplies"] = 1
        inv.horror = 1

        impl = game.card_registry.active_instances.get("aid_1")
        assert impl.activate(game.state, "test_investigator") is True
        assert "aid_1" not in inv.play_area
        assert "first_aid_lv3" in inv.discard
