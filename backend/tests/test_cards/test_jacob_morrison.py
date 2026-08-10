"""Tests for Jacob Morrison (Level 3)."""

import pytest
from backend.cards.survivor.jacob_morrison_lv3 import JacobMorrison
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
    inv_data = make_investigator_data(combat=3)
    g.register_card_data(inv_data)
    loc = make_location_data()
    g.register_card_data(loc)
    g.register_card_data(make_asset_data(
        id="jacob_morrison_lv3", name="Jacob Morrison", cost=3,
        card_class=PlayerClass.SURVIVOR, slots=[SlotType.ALLY],
        health=2, sanity=2, traits=["ally", "blessed"],
    ))
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)
    g.card_registry.register_class(JacobMorrison)
    return g


def _equip_jacob(game):
    inv = game.state.get_investigator("inv1")
    iid = game.state.next_instance_id()
    game.state.cards_in_play[iid] = CardInstance(
        instance_id=iid, card_id="jacob_morrison_lv3",
        owner_id="inv1", controller_id="inv1", slot_used=[SlotType.ALLY],
    )
    inv.play_area.append(iid)
    game.card_registry.activate_card("jacob_morrison_lv3", iid, game.event_bus)
    return iid


class TestJacobMorrison:
    def test_card_registered(self, game):
        assert "jacob_morrison_lv3" in game.card_registry.registered_cards

    def test_exhaust_turns_failure_to_success(self, game):
        """你即将失败时横置雅各布：+2技能值（差值≤2翻转）。"""
        jacob_id = _equip_jacob(game)
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]

        # 战斗3 vs 难度5：差2 → 横置并翻转
        result = game.skill_test_engine.run_test("inv1", Skill.COMBAT, 5)

        assert result.success is True
        assert game.state.get_card_instance(jacob_id).exhausted is True

    def test_no_exhaust_when_margin_too_large(self, game):
        """差值>2 时不浪费横置。"""
        jacob_id = _equip_jacob(game)
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]

        result = game.skill_test_engine.run_test("inv1", Skill.COMBAT, 6)

        assert result.success is False
        assert game.state.get_card_instance(jacob_id).exhausted is False

    def test_bless_token_readies_him(self, game):
        """你进行检定揭示祝福标记后：准备雅各布。"""
        jacob_id = _equip_jacob(game)
        game.state.get_card_instance(jacob_id).exhausted = True
        game.chaos_bag.tokens = [ChaosTokenType.BLESS]

        game.skill_test_engine.run_test("inv1", Skill.COMBAT, 1)

        assert game.state.get_card_instance(jacob_id).exhausted is False

    def test_does_not_ready_during_upkeep(self, game):
        """upkeep 中不准备（引擎就绪后立即重横置）。"""
        jacob_id = _equip_jacob(game)
        game.state.get_card_instance(jacob_id).exhausted = True

        game.upkeep_phase._ready_all()

        assert game.state.get_card_instance(jacob_id).exhausted is True
