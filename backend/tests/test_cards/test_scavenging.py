"""Tests for Scavenging (Level 0)."""

import pytest
from backend.cards.survivor.scavenging_lv0 import Scavenging
from backend.models.enums import Action, ChaosTokenType, PlayerClass, Skill
from backend.tests.conftest import (
    make_investigator_data, make_asset_data, make_location_data,
)
from backend.models.state import CardInstance
from backend.engine.game import Game


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)
    inv_data = make_investigator_data(intellect=3)
    g.register_card_data(inv_data)
    loc = make_location_data(shroud=2)
    g.register_card_data(loc)

    scav_data = make_asset_data(
        id="scavenging_lv0", name="Scavenging", cost=1,
        card_class=PlayerClass.SURVIVOR, traits=["talent"],
    )
    g.register_card_data(scav_data)
    g.register_card_data(make_asset_data(id="test_item", traits=["item"]))
    g.register_card_data(make_asset_data(id="test_tome", traits=["tome"]))

    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)
    g.card_registry.register_class(Scavenging)
    return g


def _put_scavenging_in_play(game):
    inv = game.state.get_investigator("inv1")
    iid = game.state.next_instance_id()
    game.state.cards_in_play[iid] = CardInstance(
        instance_id=iid, card_id="scavenging_lv0",
        owner_id="inv1", controller_id="inv1",
    )
    inv.play_area.append(iid)
    game.card_registry.activate_card("scavenging_lv0", iid, game.event_bus)
    return iid


def _investigate(game, token):
    inv = game.state.get_investigator("inv1")
    inv.actions_remaining = 3
    game.chaos_bag.tokens = [token]
    game.action_resolver.perform_action("inv1", Action.INVESTIGATE)


class TestScavenging:
    def test_card_registered(self, game):
        assert "scavenging_lv0" in game.card_registry.registered_cards

    def test_exhausts_and_recovers_item_on_margin_2(self, game):
        """成功调查且超出≥2：横置拾荒，取回弃牌堆的道具（拾荒不弃置）。"""
        scav_id = _put_scavenging_in_play(game)
        inv = game.state.get_investigator("inv1")
        inv.discard = ["test_item"]

        _investigate(game, ChaosTokenType.PLUS_1)  # 4 vs 2，超出2

        inst = game.state.get_card_instance(scav_id)
        assert "test_item" in inv.hand
        assert "test_item" not in inv.discard
        assert inst.exhausted is True
        assert scav_id in inv.play_area          # 可刷新再用
        assert "scavenging_lv0" not in inv.discard

    def test_no_trigger_below_margin_2(self, game):
        scav_id = _put_scavenging_in_play(game)
        inv = game.state.get_investigator("inv1")
        inv.discard = ["test_item"]

        _investigate(game, ChaosTokenType.ZERO)  # 3 vs 2，仅超出1

        inst = game.state.get_card_instance(scav_id)
        assert "test_item" not in inv.hand
        assert inst.exhausted is False

    def test_no_trigger_on_failed_investigate(self, game):
        scav_id = _put_scavenging_in_play(game)
        inv = game.state.get_investigator("inv1")
        inv.discard = ["test_item"]

        _investigate(game, ChaosTokenType.AUTO_FAIL)

        inst = game.state.get_card_instance(scav_id)
        assert "test_item" not in inv.hand
        assert inst.exhausted is False

    def test_no_trigger_outside_investigate(self, game):
        """普通智力检定（非调查行动）不触发。"""
        scav_id = _put_scavenging_in_play(game)
        inv = game.state.get_investigator("inv1")
        inv.discard = ["test_item"]
        game.chaos_bag.tokens = [ChaosTokenType.PLUS_1]

        result = game.skill_test_engine.run_test("inv1", Skill.INTELLECT, 2)
        assert result.success is True

        inst = game.state.get_card_instance(scav_id)
        assert "test_item" not in inv.hand
        assert inst.exhausted is False

    def test_no_trigger_when_exhausted(self, game):
        scav_id = _put_scavenging_in_play(game)
        inv = game.state.get_investigator("inv1")
        inv.discard = ["test_item"]
        game.state.get_card_instance(scav_id).exhausted = True

        _investigate(game, ChaosTokenType.PLUS_1)

        assert "test_item" not in inv.hand

    def test_no_item_in_discard_no_trigger(self, game):
        scav_id = _put_scavenging_in_play(game)
        inv = game.state.get_investigator("inv1")
        inv.discard = ["test_tome"]  # 非道具

        _investigate(game, ChaosTokenType.PLUS_1)

        inst = game.state.get_card_instance(scav_id)
        assert inst.exhausted is False
        assert "test_tome" in inv.discard
