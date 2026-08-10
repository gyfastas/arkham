"""Tests for Leg Injury (Level 0 basic weakness)."""

import pytest
from backend.cards.neutral.leg_injury_lv0 import LegInjury
from backend.engine.draw_hooks import emit_card_drawn
from backend.engine.game import Game
from backend.models.enums import Action
from backend.tests.conftest import (
    make_event_data, make_investigator_data, make_location_data,
)


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)
    g.register_card_data(make_investigator_data())
    g.register_card_data(make_location_data(connections=["loc2"]))
    g.register_card_data(make_location_data(
        id="loc2", name="Loc2", connections=["test_location"],
    ))
    g.register_card_data(make_event_data(id="leg_injury_lv0", name="Leg Injury"))
    g.add_investigator("inv1", g.state.get_card_data("test_investigator"),
                       starting_location="test_location")
    g.add_location("test_location", g.state.get_card_data("test_location"))
    g.add_location("loc2", g.state.get_card_data("loc2"))
    g.card_registry.register_class(LegInjury)
    return g


def _draw(game):
    inv = game.state.get_investigator("inv1")
    inv.hand.append("leg_injury_lv0")
    emit_card_drawn(game.state, game.event_bus, game.card_registry,
                    inv, "leg_injury_lv0", chaos_bag=game.chaos_bag)
    return next(
        i for i in game.card_registry.active_instances.values()
        if isinstance(i, LegInjury)
    )


class TestLegInjury:
    def test_revelation_enters_threat_area(self, game):
        """显现：放入威胁区域。"""
        _draw(game)
        inv = game.state.get_investigator("inv1")
        assert any(
            game.state.get_card_instance(iid).card_id == "leg_injury_lv0"
            for iid in inv.threat_area
        )

    def test_blocks_move_evade_resign_after_move(self, game):
        """执行移动后：本回合不能再移动/躲避/辞职（其他行动不受影响）。"""
        impl = _draw(game)
        game.action_resolver.perform_action(
            "inv1", Action.MOVE, destination="loc2",
        )
        assert impl.can_take_action(game.state, "inv1", Action.MOVE) is False
        assert impl.can_take_action(game.state, "inv1", Action.EVADE) is False
        assert impl.can_take_action(game.state, "inv1", Action.RESIGN) is False
        assert impl.can_take_action(game.state, "inv1", Action.FIGHT) is True

    def test_heal_discards(self, game):
        """作为1点伤害被治愈：丢弃。"""
        impl = _draw(game)
        inv = game.state.get_investigator("inv1")
        assert impl.heal(game.state, "inv1") is True
        assert "leg_injury_lv0" in inv.discard
        assert all(
            game.state.get_card_instance(iid) is None
            or game.state.get_card_instance(iid).card_id != "leg_injury_lv0"
            for iid in inv.threat_area
        )
