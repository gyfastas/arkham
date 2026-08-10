"""Tests for Truth from Fiction (Level 0).

官方：只有当你所在地点有线索时才能打出。在你控制的1张支援卡上放置
2秘密。
"""

import pytest

from backend.cards.seeker.truth_from_fiction_lv0 import TruthFromFiction
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import GameEvent
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_asset_data, make_investigator_data, make_location_data,
)


@pytest.fixture
def game():
    g = Game("test_truth_from_fiction")
    g.chaos_bag.seed(42)

    inv_data = make_investigator_data()
    g.register_card_data(inv_data)
    loc_data = make_location_data(id="loc_a")
    g.register_card_data(loc_data)
    g.add_investigator("player", inv_data, starting_location="loc_a")
    g.add_location("loc_a", loc_data, clues=2)

    g.register_card_data(make_asset_data(
        id="old_book_of_lore_lv0", name="Old Book of Lore",
        uses={"secrets": 3}))
    inst = CardInstance(
        instance_id="inst_obol", card_id="old_book_of_lore_lv0",
        owner_id="player", controller_id="player",
    )
    inst.uses = {"secrets": 3}
    g.state.cards_in_play["inst_obol"] = inst
    g.state.get_investigator("player").play_area.append("inst_obol")

    g.card_registry.register_class(TruthFromFiction)
    g.card_registry.activate_card(
        "truth_from_fiction_lv0", "impl_tff", g.event_bus,
        chaos_bag=g.chaos_bag)
    return g


def _play(game, **extra):
    ctx = EventContext(
        game_state=game.state, event=GameEvent.CARD_PLAYED,
        investigator_id="player",
        extra={"card_id": "truth_from_fiction_lv0", **extra},
    )
    game.event_bus.emit(ctx)
    return ctx


class TestTruthFromFiction:
    def test_places_two_secrets_on_asset(self, game):
        """地点有线索：你控制的支援卡+2秘密（3→5）。"""
        inst = game.state.get_card_instance("inst_obol")
        ctx = _play(game)
        assert ctx.extra.get("truth_from_fiction_asset") == "inst_obol"
        assert inst.uses["secrets"] == 5

    def test_no_clue_at_location_no_effect(self, game):
        """地点无线索：效果不生效。"""
        game.state.get_location("loc_a").clues = 0
        inst = game.state.get_card_instance("inst_obol")
        ctx = _play(game)
        assert ctx.extra.get("truth_from_fiction_failed") == "no_clue"
        assert inst.uses["secrets"] == 3
