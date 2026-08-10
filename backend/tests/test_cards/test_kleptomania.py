"""Tests for Kleptomania (Level 0 basic weakness)."""

import pytest
from backend.cards.neutral.kleptomania_lv0 import Kleptomania
from backend.engine.draw_hooks import emit_card_drawn
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import GameEvent
from backend.tests.conftest import (
    make_asset_data, make_investigator_data, make_location_data,
)


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)
    g.register_card_data(make_investigator_data())
    g.register_card_data(make_investigator_data(id="inv2_data", name="Inv2"))
    g.register_card_data(make_location_data())
    g.register_card_data(make_asset_data(id="kleptomania_lv0", name="Kleptomania", cost=0))
    g.add_investigator("inv1", g.state.get_card_data("test_investigator"),
                       starting_location="test_location")
    g.add_investigator("inv2", g.state.get_card_data("inv2_data"),
                       starting_location="test_location")
    g.add_location("test_location", g.state.get_card_data("test_location"))
    g.card_registry.register_class(Kleptomania)
    return g


def _draw(game):
    inv = game.state.get_investigator("inv1")
    inv.hand.append("kleptomania_lv0")
    emit_card_drawn(game.state, game.event_bus, game.card_registry,
                    inv, "kleptomania_lv0", chaos_bag=game.chaos_bag)
    return next(
        i for i in game.card_registry.active_instances.values()
        if isinstance(i, Kleptomania)
    )


class TestKleptomania:
    def test_revelation_puts_into_play(self, game):
        """显现：放入你的战场。"""
        _draw(game)
        inv = game.state.get_investigator("inv1")
        assert "kleptomania_lv0" not in inv.hand
        assert any(
            game.state.get_card_instance(iid).card_id == "kleptomania_lv0"
            for iid in inv.play_area
        )

    def test_end_of_turn_horror(self, game):
        """强制 - 回合结束时：受到1点恐惧。"""
        _draw(game)
        inv = game.state.get_investigator("inv1")
        game.event_bus.emit(EventContext(
            game_state=game.state, event=GameEvent.INVESTIGATOR_TURN_ENDS,
            investigator_id="inv1",
        ))
        assert inv.horror == 1

    def test_activate_steals_2_resources_and_shuffles_back(self, game):
        """[行动] 夺取同地点调查员2资源，然后洗入你的牌组。"""
        impl = _draw(game)
        inv1 = game.state.get_investigator("inv1")
        inv2 = game.state.get_investigator("inv2")
        inv2.resources = 3
        before = inv1.resources
        assert impl.activate(game.state, "inv1") is True
        assert inv2.resources == 1
        assert inv1.resources == before + 2
        assert "kleptomania_lv0" in inv1.deck
        assert not any(
            game.state.get_card_instance(iid) is not None
            and game.state.get_card_instance(iid).card_id == "kleptomania_lv0"
            for iid in inv1.play_area
        )
