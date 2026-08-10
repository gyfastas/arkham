"""Tests for Hallowed Mirror (Level 0). (05313)

入场后：1张舒缓旋律入手，2张洗入牌库；离场时全部移出游戏。
"""

import pytest
from backend.cards.guardian.hallowed_mirror_lv0 import HallowedMirror
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import GameEvent, PlayerClass, SlotType
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_asset_data, make_event_data, make_investigator_data,
    make_location_data,
)


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)
    inv_data = make_investigator_data()
    g.register_card_data(inv_data)
    g.register_card_data(make_location_data())
    g.register_card_data(make_asset_data(
        id="hallowed_mirror_lv0", name="Hallowed Mirror", cost=2,
        card_class=PlayerClass.GUARDIAN, slots=[SlotType.ACCESSORY],
        traits=["item", "relic", "occult", "blessed"],
    ))
    g.register_card_data(make_event_data(
        id="soothing_melody_lv0", name="Soothing Melody", cost=0,
        card_class=PlayerClass.GUARDIAN,
    ))
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", g.state.get_card_data("test_location"), clues=0)
    g.card_registry.register_class(HallowedMirror)

    inv = g.state.get_investigator("inv1")
    inst = CardInstance(
        instance_id="mirror_1", card_id="hallowed_mirror_lv0",
        owner_id="inv1", controller_id="inv1",
        slot_used=[SlotType.ACCESSORY],
    )
    g.state.cards_in_play["mirror_1"] = inst
    inv.play_area.append("mirror_1")
    g.card_registry.activate_card("hallowed_mirror_lv0", "mirror_1", g.event_bus)
    return g


class TestHallowedMirror:
    def test_enters_play_fetches_melodies(self, game):
        """入场：1张入手、2张入牌库。"""
        inv = game.state.get_investigator("inv1")
        inv.hand = []
        inv.deck = []

        ctx = EventContext(
            game_state=game.state, event=GameEvent.CARD_ENTERS_PLAY,
            investigator_id="inv1", target="mirror_1",
            extra={"card_id": "hallowed_mirror_lv0"},
        )
        game.event_bus.emit(ctx)

        assert inv.hand == ["soothing_melody_lv0"]
        assert inv.deck.count("soothing_melody_lv0") == 2
        assert ctx.extra["hallowed_mirror_bonded"] is True

    def test_leaves_play_sets_aside_all(self, game):
        """离场：手牌/牌库/弃牌堆中的舒缓旋律全部移出游戏。"""
        inv = game.state.get_investigator("inv1")
        inv.hand = ["soothing_melody_lv0"]
        inv.deck = ["soothing_melody_lv0"]
        inv.discard = ["soothing_melody_lv0"]

        ctx = EventContext(
            game_state=game.state, event=GameEvent.CARD_LEAVES_PLAY,
            investigator_id="inv1", target="mirror_1",
            extra={"card_id": "hallowed_mirror_lv0"},
        )
        game.event_bus.emit(ctx)

        assert "soothing_melody_lv0" not in inv.hand
        assert "soothing_melody_lv0" not in inv.deck
        assert "soothing_melody_lv0" not in inv.discard
        assert game.state.scenario.vars["out_of_play"].count(
            "soothing_melody_lv0") == 3
