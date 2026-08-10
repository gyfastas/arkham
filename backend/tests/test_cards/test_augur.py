"""Tests for Augur (Level 0)."""

import pytest

from backend.cards.survivor.augur_lv0 import Augur
from backend.engine.game import Game
from backend.models.enums import Action, ChaosTokenType, Skill
from backend.models.state import CardInstance
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
    augur = make_asset_data(
        id="augur_lv0", name="Augur", cost=1, traits=["ally", "creature"])
    augur.fast = True
    g.register_card_data(augur)
    g.register_card_data(make_asset_data(
        id="hope_lv0", name="Hope", cost=1, traits=["ally", "creature"]))
    g.register_card_data(make_asset_data(
        id="zeal_lv0", name="Zeal", cost=1, traits=["ally", "creature"]))
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)
    g.card_registry.register_class(Augur)
    return g


def _put_into_play(game, card_id, instance_id):
    inv = game.state.get_investigator("inv1")
    game.state.cards_in_play[instance_id] = CardInstance(
        instance_id=instance_id, card_id=card_id,
        owner_id="inv1", controller_id="inv1",
    )
    inv.play_area.append(instance_id)


class TestAugur:
    def test_card_registered(self, game):
        assert "augur_lv0" in game.card_registry.registered_cards

    def test_forced_discards_hope_and_zeal_on_enter(self, game):
        """强制：预见入场后丢弃希望和热诚。"""
        _put_into_play(game, "hope_lv0", "hope_1")
        _put_into_play(game, "zeal_lv0", "zeal_1")
        inv = game.state.get_investigator("inv1")
        inv.resources = 5
        inv.hand = ["augur_lv0"]

        assert game.action_resolver.perform_action(
            "inv1", Action.PLAY, card_id="augur_lv0") is True
        assert "hope_1" not in inv.play_area
        assert "zeal_1" not in inv.play_area
        assert "hope_lv0" in inv.discard
        assert "zeal_lv0" in inv.discard

    def test_discard_activate_auto_success_and_revive(self, game):
        """丢弃预见的调查：基础智力5、自动成功；收尾洗回牌库并复活希望。"""
        _put_into_play(game, "hope_lv0", "hope_1")
        inv = game.state.get_investigator("inv1")
        inv.resources = 5
        inv.hand = ["augur_lv0"]
        game.action_resolver.perform_action(
            "inv1", Action.PLAY, card_id="augur_lv0")
        # hope 被强制丢弃，augur 已入场
        augur_iid = next(i for i in inv.play_area
                         if game.state.get_card_instance(i).card_id == "augur_lv0")
        impl = game.card_registry.active_instances[augur_iid]

        assert impl.activate(game.state, "inv1", discard=True) is True
        assert "augur_lv0" in inv.discard

        # 以基础智力5调查一个不可能的难度：自动成功
        game.chaos_bag.tokens = [ChaosTokenType.MINUS_3]
        result = game.skill_test_engine.run_test(
            "inv1", Skill.INTELLECT, 99)
        assert result.extra.get("augur_auto_success") is True
        assert result.success is True

        # 收尾：预见洗回牌库（简化置底），希望从弃牌堆复活入场
        assert "augur_lv0" in inv.deck
        revived = [game.state.get_card_instance(i).card_id
                   for i in inv.play_area]
        assert "hope_lv0" in revived

    def test_exhaust_activate_no_auto_success(self, game):
        """仅消耗（不丢弃）：基础智力5，但不自动成功。"""
        inv = game.state.get_investigator("inv1")
        inv.resources = 5
        inv.hand = ["augur_lv0"]
        game.action_resolver.perform_action(
            "inv1", Action.PLAY, card_id="augur_lv0")
        augur_iid = next(i for i in inv.play_area
                         if game.state.get_card_instance(i).card_id == "augur_lv0")
        impl = game.card_registry.active_instances[augur_iid]

        assert impl.activate(game.state, "inv1") is True
        inst = game.state.get_card_instance(augur_iid)
        assert inst.exhausted is True

        # 难度6 > 基础5（无投入）：失败，不翻转
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]
        result = game.skill_test_engine.run_test(
            "inv1", Skill.INTELLECT, 6)
        assert result.modified_skill == 5
        assert result.success is False
