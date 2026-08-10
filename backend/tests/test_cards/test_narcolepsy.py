"""Tests for Narcolepsy (Level 0 basic weakness)."""

import pytest
from backend.cards.neutral.narcolepsy_lv0 import Narcolepsy
from backend.engine.draw_hooks import emit_card_drawn
from backend.engine.game import Game
from backend.tests.conftest import (
    make_event_data, make_investigator_data, make_location_data,
)


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)
    g.register_card_data(make_investigator_data())
    g.register_card_data(make_location_data())
    g.register_card_data(make_event_data(id="narcolepsy_lv0", name="Narcolepsy"))
    g.add_investigator("inv1", g.state.get_card_data("test_investigator"),
                       starting_location="test_location")
    g.add_location("test_location", g.state.get_card_data("test_location"))
    g.card_registry.register_class(Narcolepsy)
    return g


def _draw(game):
    inv = game.state.get_investigator("inv1")
    inv.hand.append("narcolepsy_lv0")
    emit_card_drawn(game.state, game.event_bus, game.card_registry,
                    inv, "narcolepsy_lv0", chaos_bag=game.chaos_bag)
    return next(
        i for i in game.card_registry.active_instances.values()
        if isinstance(i, Narcolepsy)
    )


def _in_threat(game):
    inv = game.state.get_investigator("inv1")
    return any(
        game.state.get_card_instance(iid) is not None
        and game.state.get_card_instance(iid).card_id == "narcolepsy_lv0"
        for iid in inv.threat_area
    )


class TestNarcolepsy:
    def test_revelation_enters_threat_area_and_blocks_actions(self, game):
        """显现：放入威胁区域；期间不能执行行动（供会话层查询）。"""
        impl = _draw(game)
        assert _in_threat(game) is True
        assert impl.can_take_action(game.state, "inv1") is False

    def test_discarded_after_taking_damage(self, game):
        """强制 - 受到伤害后：丢弃。"""
        _draw(game)
        game.damage_engine.deal_damage("inv1", damage=1)
        assert _in_threat(game) is False
        inv = game.state.get_investigator("inv1")
        assert "narcolepsy_lv0" in inv.discard

    def test_wake_up_discards(self, game):
        """[行动] "醒来！"：丢弃。"""
        impl = _draw(game)
        assert impl.activate_wake_up(game.state, "inv1") is True
        assert _in_threat(game) is False
