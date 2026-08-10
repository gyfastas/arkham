"""Tests for Guiding Spirit (Level 1)."""

import pytest
from backend.cards.survivor.guiding_spirit_lv1 import GuidingSpirit
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
    inv_data = make_investigator_data(intellect=3)
    g.register_card_data(inv_data)
    loc = make_location_data()
    g.register_card_data(loc)
    g.register_card_data(make_asset_data(
        id="guiding_spirit_lv1", name="Guiding Spirit", cost=1,
        card_class=PlayerClass.SURVIVOR, slots=[SlotType.ALLY],
        sanity=3, traits=["ally", "geist"],
    ))
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)
    g.card_registry.register_class(GuidingSpirit)
    return g


def _equip_spirit(game):
    inv = game.state.get_investigator("inv1")
    iid = game.state.next_instance_id()
    game.state.cards_in_play[iid] = CardInstance(
        instance_id=iid, card_id="guiding_spirit_lv1",
        owner_id="inv1", controller_id="inv1", slot_used=[SlotType.ALLY],
    )
    inv.play_area.append(iid)
    game.card_registry.activate_card("guiding_spirit_lv1", iid, game.event_bus)
    return iid


class TestGuidingSpirit:
    def test_card_registered(self, game):
        assert "guiding_spirit_lv1" in game.card_registry.registered_cards

    def test_intellect_bonus(self, game):
        """在场时 +1 智力。"""
        _equip_spirit(game)
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]
        result = game.skill_test_engine.run_test("inv1", Skill.INTELLECT, 4)
        assert result.modified_skill == 4  # 3 + 1
        assert result.success is True

    def test_horror_soaked_before_investigator(self, game):
        """非直接恐惧先由引路精灵承担。"""
        spirit_id = _equip_spirit(game)
        inv = game.state.get_investigator("inv1")

        game.damage_engine.deal_damage("inv1", horror=2)

        inst = game.state.get_card_instance(spirit_id)
        assert inst.horror == 2
        assert inv.horror == 0

    def test_defeated_by_horror_is_exiled(self, game):
        """被恐惧击败时放逐（不进弃牌堆）。"""
        spirit_id = _equip_spirit(game)
        inv = game.state.get_investigator("inv1")

        game.damage_engine.deal_damage("inv1", horror=3)

        assert spirit_id not in inv.play_area
        assert game.state.get_card_instance(spirit_id) is None
        assert "guiding_spirit_lv1" not in inv.discard
        assert "guiding_spirit_lv1" in game.state.scenario.vars["exiled_cards"]
        assert inv.horror == 0
