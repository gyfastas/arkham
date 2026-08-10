"""Tests for Bangle of Jinxes (Level 1)."""

import pytest

from backend.cards.survivor.bangle_of_jinxes_lv1 import BangleOfJinxes
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import Action, ChaosTokenType, GameEvent, Skill, SlotType
from backend.tests.conftest import (
    make_asset_data, make_investigator_data, make_location_data,
)


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)
    inv_data = make_investigator_data(intellect=3)
    g.register_card_data(inv_data)
    loc = make_location_data()
    g.register_card_data(loc)
    g.register_card_data(make_asset_data(
        id="bangle_of_jinxes_lv1", name="Bangle of Jinxes", cost=2,
        slots=[SlotType.ACCESSORY], traits=["item", "charm"],
        uses={"charges": 1}))
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)
    g.card_registry.register_class(BangleOfJinxes)
    return g


def _play_bangle(game):
    inv = game.state.get_investigator("inv1")
    inv.resources = 5
    inv.hand = ["bangle_of_jinxes_lv1"]
    assert game.action_resolver.perform_action(
        "inv1", Action.PLAY, card_id="bangle_of_jinxes_lv1") is True
    iid = next(i for i in inv.play_area
               if game.state.get_card_instance(i).card_id
               == "bangle_of_jinxes_lv1")
    return inv, iid, game.card_registry.active_instances[iid]


class TestBangleOfJinxes:
    def test_card_registered(self, game):
        assert "bangle_of_jinxes_lv1" in game.card_registry.registered_cards

    def test_spend_charge_boosts_test_once(self, game):
        """花1充能：本次检定+2；每次检定限1次。"""
        inv, iid, impl = _play_bangle(game)
        assert impl.spend(game.state, "inv1") is True
        assert game.state.get_card_instance(iid).uses["charges"] == 0
        # 每次检定限1次
        assert impl.spend(game.state, "inv1") is False

        game.chaos_bag.tokens = [ChaosTokenType.ZERO]
        result = game.skill_test_engine.run_test("inv1", Skill.INTELLECT, 5)
        assert result.modified_skill == 5
        assert result.success is True

    def test_enemy_attack_places_charge(self, game):
        """敌人攻击你后：放置1充能。"""
        inv, iid, impl = _play_bangle(game)
        inst = game.state.get_card_instance(iid)
        inst.uses["charges"] = 0
        game.event_bus.emit(EventContext(
            game_state=game.state, event=GameEvent.ENEMY_ATTACKS,
            investigator_id="inv1", enemy_id="enemy_1",
        ))
        assert inst.uses["charges"] == 1
