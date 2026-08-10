"""Tests for Mitch Brown (Level 0)."""

import pytest
from backend.cards.neutral.mitch_brown_lv0 import MitchBrown
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import Action, GameEvent, SlotType
from backend.tests.conftest import (
    make_asset_data, make_investigator_data, make_location_data,
)


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)
    g.register_card_data(make_investigator_data())
    g.register_card_data(make_location_data())
    g.register_card_data(make_asset_data(
        id="mitch_brown_lv0", name="Mitch Brown", cost=3,
        slots=[SlotType.ALLY],
    ))
    g.add_investigator("inv1", g.state.get_card_data("test_investigator"),
                       starting_location="test_location")
    g.add_location("test_location", g.state.get_card_data("test_location"))
    g.card_registry.register_class(MitchBrown)
    inv = g.state.get_investigator("inv1")
    inv.hand.append("mitch_brown_lv0")
    inv.resources = 5
    return g


class TestMitchBrown:
    def test_grants_2_additional_ally_slots(self, game):
        """进场：+2盟友槽位（基础1→3）。"""
        mgr = game.slot_managers["inv1"]
        assert mgr.effective_limit(SlotType.ALLY) == 1
        game.action_resolver.perform_action(
            "inv1", Action.PLAY, card_id="mitch_brown_lv0",
        )
        assert mgr.effective_limit(SlotType.ALLY) == 3

    def test_slots_removed_on_leaves_play(self, game):
        """离场：收回2个槽位。"""
        game.action_resolver.perform_action(
            "inv1", Action.PLAY, card_id="mitch_brown_lv0",
        )
        mgr = game.slot_managers["inv1"]
        inst_id = next(
            iid for iid, ci in game.state.cards_in_play.items()
            if ci.card_id == "mitch_brown_lv0"
        )
        game.event_bus.emit(EventContext(
            game_state=game.state, event=GameEvent.CARD_LEAVES_PLAY,
            investigator_id="inv1", target=inst_id,
            extra={"card_id": "mitch_brown_lv0"},
        ))
        assert mgr.effective_limit(SlotType.ALLY) == 1
