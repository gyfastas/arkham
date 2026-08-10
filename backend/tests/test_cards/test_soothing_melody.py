"""Tests for Soothing Melody (Level 0). (05314)

治愈同地点调查员/盟友共2点伤害或恐惧，抽1张牌。
"""

import pytest

from backend.cards.guardian.soothing_melody_lv0 import SoothingMelody
from backend.engine.game import Game
from backend.models.enums import Action, PlayerClass
from backend.tests.conftest import (
    make_event_data, make_investigator_data, make_location_data,
)


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)
    inv_data = make_investigator_data()
    g.register_card_data(inv_data)
    loc = make_location_data()
    g.register_card_data(loc)
    g.register_card_data(make_event_data(
        id="soothing_melody_lv0", name="Soothing Melody", cost=0,
        card_class=PlayerClass.GUARDIAN,
    ))
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", g.state.get_card_data("test_location"))
    g.card_registry.register_class(SoothingMelody)
    inv = g.state.get_investigator("inv1")
    inv.actions_remaining = 3
    return g


class TestSoothingMelody:
    def test_auto_heal_and_draw(self, game):
        """自动分配（先伤害后恐惧，共2点）并抽1张牌。"""
        inv = game.state.get_investigator("inv1")
        inv.hand.append("soothing_melody_lv0")
        inv.damage = 1
        inv.horror = 2
        inv.deck = ["top_card"]

        ok = game.action_resolver.perform_action(
            "inv1", Action.PLAY, card_id="soothing_melody_lv0",
        )
        assert ok is True
        assert inv.damage == 0
        assert inv.horror == 1  # 共治愈2点
        assert "top_card" in inv.hand

    def test_heal_plan_override(self, game):
        """会话层分配方案：全部治愈恐惧（直接发事件以携带 heal_plan）。"""
        from backend.engine.event_bus import EventContext
        from backend.models.enums import GameEvent

        impl = SoothingMelody("sm_1")
        impl.register(game.event_bus, "sm_1")
        inv = game.state.get_investigator("inv1")
        inv.damage = 1
        inv.horror = 2

        ctx = EventContext(
            game_state=game.state, event=GameEvent.CARD_PLAYED,
            investigator_id="inv1",
            extra={
                "card_id": "soothing_melody_lv0",
                "heal_plan": [
                    {"target": "self", "kind": "horror", "amount": 2},
                ],
            },
        )
        game.event_bus.emit(ctx)
        assert inv.horror == 0
        assert inv.damage == 1
