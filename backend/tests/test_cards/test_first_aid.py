"""Tests for First Aid (Level 0)."""

import pytest
from backend.cards.guardian.first_aid_lv0 import FirstAid
from backend.models.enums import SlotType
from backend.models.state import CardInstance
from backend.tests.conftest import make_asset_data


@pytest.fixture
def aid_game(game):
    game.register_card_data(make_asset_data(
        id="first_aid_lv0", name="First Aid", traits=["talent", "science"],
        uses={"supplies": 3},
    ))
    inv = game.state.get_investigator("test_investigator")
    inst = CardInstance(
        instance_id="aid_1", card_id="first_aid_lv0",
        owner_id="test_investigator", controller_id="test_investigator",
        uses={"supplies": 3},
    )
    game.state.cards_in_play["aid_1"] = inst
    inv.play_area.append("aid_1")

    game.card_registry.register_class(FirstAid)
    game.card_registry.activate_card("first_aid_lv0", "aid_1", game.event_bus)
    return game


class TestFirstAid:
    def test_card_id(self):
        assert FirstAid.card_id == "first_aid_lv0"

    def test_heal_1_damage_spends_supply(self, aid_game):
        """花1补给治愈1点伤害。"""
        game = aid_game
        inv = game.state.get_investigator("test_investigator")
        inv.damage = 2

        impl = game.card_registry.active_instances.get("aid_1")
        assert impl.activate(game.state, "test_investigator") is True
        assert inv.damage == 1
        inst = game.state.get_card_instance("aid_1")
        assert inst.uses["supplies"] == 2

    def test_heal_1_horror_when_no_damage(self, aid_game):
        """无伤害时自动治愈1点恐惧。"""
        game = aid_game
        inv = game.state.get_investigator("test_investigator")
        inv.horror = 2

        impl = game.card_registry.active_instances.get("aid_1")
        assert impl.activate(game.state, "test_investigator") is True
        assert inv.horror == 1

    def test_explicit_heal_choice(self, aid_game):
        """可显式选择治愈伤害或恐惧。"""
        game = aid_game
        inv = game.state.get_investigator("test_investigator")
        inv.damage = 1
        inv.horror = 1

        impl = game.card_registry.active_instances.get("aid_1")
        assert impl.activate(game.state, "test_investigator", heal="horror") is True
        assert inv.horror == 0
        assert inv.damage == 1

    def test_no_heal_when_healthy(self, aid_game):
        """目标没有伤害/恐惧时不扣补给。"""
        game = aid_game
        impl = game.card_registry.active_instances.get("aid_1")
        assert impl.activate(game.state, "test_investigator") is False
        inst = game.state.get_card_instance("aid_1")
        assert inst.uses["supplies"] == 3

    def test_discard_when_supplies_exhausted(self, aid_game):
        """补给耗尽后弃置急救。"""
        game = aid_game
        inv = game.state.get_investigator("test_investigator")
        inst = game.state.get_card_instance("aid_1")
        inst.uses["supplies"] = 1
        inv.damage = 1

        impl = game.card_registry.active_instances.get("aid_1")
        assert impl.activate(game.state, "test_investigator") is True
        assert "aid_1" not in inv.play_area
        assert "aid_1" not in game.state.cards_in_play
        assert "first_aid_lv0" in inv.discard

    def test_cannot_heal_investigator_elsewhere(self, aid_game):
        """目标调查员必须在同一地点。"""
        game = aid_game
        from backend.tests.conftest import make_investigator_data
        other_data = make_investigator_data(id="inv2")
        game.register_card_data(other_data)
        game.add_investigator("inv2", other_data, starting_location="test_location")
        other = game.state.get_investigator("inv2")
        other.location_id = "elsewhere"
        other.damage = 1

        impl = game.card_registry.active_instances.get("aid_1")
        assert impl.activate(game.state, "test_investigator",
                             target_investigator_id="inv2") is False
        assert other.damage == 1
