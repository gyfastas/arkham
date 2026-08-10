"""Tests for Miss Doyle (Level 1)."""

import pytest
from backend.cards.survivor.miss_doyle_lv1 import MissDoyle
from backend.models.enums import (
    Action, GameEvent, PlayerClass, SlotType,
)
from backend.tests.conftest import (
    make_asset_data, make_investigator_data, make_location_data,
)
from backend.engine.event_bus import EventContext
from backend.engine.game import Game


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)
    inv_data = make_investigator_data()
    g.register_card_data(inv_data)
    loc = make_location_data()
    g.register_card_data(loc)
    g.register_card_data(make_asset_data(
        id="miss_doyle_lv1", name="Miss Doyle", cost=3,
        card_class=PlayerClass.SURVIVOR, slots=[SlotType.ALLY],
        health=2, sanity=2, traits=["ally", "creature", "dreamlands"]))
    for cid in ("hope_lv0", "zeal_lv0", "augur_lv0"):
        g.register_card_data(make_asset_data(
            id=cid, name=cid, cost=1, card_class=PlayerClass.SURVIVOR,
            traits=["ally", "creature", "dreamlands"]))
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)
    g.card_registry.register_class(MissDoyle)
    return g


def _play_doyle(game):
    inv = game.state.get_investigator("inv1")
    inv.hand = ["miss_doyle_lv1"]
    inv.resources = 5
    assert game.action_resolver.perform_action(
        "inv1", Action.PLAY, card_id="miss_doyle_lv1") is True
    return inv.play_area[0]


class TestMissDoyle:
    def test_card_registered(self, game):
        assert "miss_doyle_lv1" in game.card_registry.registered_cards

    def test_enters_play_summons_bonded_cat(self, game):
        """入场：1只羁绊猫入场（固定顺序 hope 优先），其余洗入牌库。"""
        doyle_id = _play_doyle(game)
        inv = game.state.get_investigator("inv1")

        # 多伊尔 + 霍普在场
        played = [game.state.get_card_instance(iid).card_id
                  for iid in inv.play_area]
        assert "miss_doyle_lv1" in played
        assert "hope_lv0" in played
        # 另两只洗入牌库
        assert sorted(cid for cid in inv.deck
                      if cid in ("zeal_lv0", "augur_lv0")) == \
            ["augur_lv0", "zeal_lv0"]

    def test_leaves_play_sets_cats_aside(self, game):
        """离场：所有羁绊猫移出游戏（在场/牌库皆然）。"""
        doyle_id = _play_doyle(game)
        inv = game.state.get_investigator("inv1")

        game.event_bus.emit(EventContext(
            game_state=game.state, event=GameEvent.CARD_LEAVES_PLAY,
            investigator_id="inv1", target=doyle_id,
            extra={"card_id": "miss_doyle_lv1"},
        ))

        out = game.state.scenario.vars["out_of_play"]
        assert sorted(out) == ["augur_lv0", "hope_lv0", "zeal_lv0"]
        played = [game.state.get_card_instance(iid).card_id
                  for iid in inv.play_area]
        assert "hope_lv0" not in played
        assert not any(cid in inv.deck
                       for cid in ("hope_lv0", "zeal_lv0", "augur_lv0"))
