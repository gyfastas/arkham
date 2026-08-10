"""Tests for Plucky (Level 3)."""

import pytest
from backend.cards.survivor.plucky_lv3 import PluckyLv3
from backend.models.enums import ChaosTokenType, PlayerClass, Skill
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_asset_data, make_investigator_data, make_location_data,
)
from backend.engine.game import Game


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)
    inv_data = make_investigator_data(willpower=3, intellect=3)
    g.register_card_data(inv_data)
    loc = make_location_data()
    g.register_card_data(loc)
    g.register_card_data(make_asset_data(
        id="plucky_lv3", name="Plucky", cost=0,
        card_class=PlayerClass.SURVIVOR, health=1, sanity=3,
        traits=["talent", "composure"],
    ))
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)
    g.card_registry.register_class(PluckyLv3)
    return g


def _equip_plucky(game):
    inv = game.state.get_investigator("inv1")
    iid = game.state.next_instance_id()
    game.state.cards_in_play[iid] = CardInstance(
        instance_id=iid, card_id="plucky_lv3",
        owner_id="inv1", controller_id="inv1",
    )
    inv.play_area.append(iid)
    game.card_registry.activate_card("plucky_lv3", iid, game.event_bus)
    return iid


class TestPluckyLv3:
    def test_card_registered(self, game):
        assert "plucky_lv3" in game.card_registry.registered_cards

    def test_passive_willpower_and_intellect(self, game):
        """在场时 +1 意志、+1 智力。"""
        _equip_plucky(game)
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]
        r1 = game.skill_test_engine.run_test("inv1", Skill.WILLPOWER, 4)
        assert r1.modified_skill == 4
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]
        r2 = game.skill_test_engine.run_test("inv1", Skill.INTELLECT, 4)
        assert r2.modified_skill == 4

    def test_spend_boosts_skill(self, game):
        """花1资源：本次检定再 +1（与被动叠加为+2）。"""
        plucky_id = _equip_plucky(game)
        inv = game.state.get_investigator("inv1")
        inv.resources = 2
        impl = game.card_registry.active_instances[plucky_id]

        assert impl.spend(game.state, "inv1", Skill.WILLPOWER) is True
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]
        result = game.skill_test_engine.run_test("inv1", Skill.WILLPOWER, 5)
        assert result.modified_skill == 5  # 3 + 1被动 + 1支付
        assert inv.resources == 1

    def test_soaks_damage_and_horror_first(self, game):
        """非直接伤害/恐惧必须先分给有胆有识。"""
        plucky_id = _equip_plucky(game)
        inv = game.state.get_investigator("inv1")

        game.damage_engine.deal_damage("inv1", damage=1)  # 生命1 → 击败
        assert plucky_id not in inv.play_area
        assert "plucky_lv3" in inv.discard
        assert inv.damage == 0

        # 重新装备测恐惧
        plucky_id2 = _equip_plucky(game)
        game.damage_engine.deal_damage("inv1", horror=2)
        inst = game.state.get_card_instance(plucky_id2)
        assert inst.horror == 2
        assert inv.horror == 0
