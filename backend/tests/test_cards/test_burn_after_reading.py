"""Tests for Burn After Reading (Level 1)."""

import pytest

from backend.cards.survivor.burn_after_reading_lv1 import BurnAfterReading
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import Action, GameEvent
from backend.tests.conftest import (
    make_event_data, make_investigator_data, make_location_data,
)


@pytest.fixture
def game():
    g = Game("test")
    inv_data = make_investigator_data()
    g.register_card_data(inv_data)
    loc = make_location_data(clue_value=4)
    g.register_card_data(loc)
    g.register_card_data(make_event_data(
        id="burn_after_reading_lv1", name="Burn After Reading", cost=1))
    lv2 = make_event_data(id="lv2_card", name="Level 2 Card", cost=1)
    lv2.level = 2
    g.register_card_data(lv2)
    lv0 = make_event_data(id="lv0_card", name="Level 0 Card", cost=1)
    lv0.level = 0
    g.register_card_data(lv0)
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=4)
    g.card_registry.register_class(BurnAfterReading)
    return g


class TestBurnAfterReading:
    def test_card_registered(self, game):
        assert "burn_after_reading_lv1" in game.card_registry.registered_cards

    def test_exile_lv2_discovers_clues_and_removes_doom(self, game):
        """放逐等级2手牌：发现2线索，密谋-1毁灭，本卡回合结束放逐。"""
        inv = game.state.get_investigator("inv1")
        inv.resources = 5
        inv.hand = ["burn_after_reading_lv1", "lv2_card"]
        game.state.scenario.doom_on_agenda = 2

        assert game.action_resolver.perform_action(
            "inv1", Action.PLAY, card_id="burn_after_reading_lv1") is True
        assert "lv2_card" in game.state.scenario.vars["exiled_cards"]
        assert inv.clues == 2
        assert game.state.get_location("test_location").clues == 2
        assert game.state.scenario.doom_on_agenda == 1

        # 本卡以放逐代替弃置（ROUND_ENDS 清理）
        assert "burn_after_reading_lv1" in inv.discard  # 结算后先入弃牌堆
        game.event_bus.emit(EventContext(
            game_state=game.state, event=GameEvent.ROUND_ENDS))
        assert "burn_after_reading_lv1" not in inv.discard
        assert "burn_after_reading_lv1" in \
            game.state.scenario.vars["exiled_cards"]

    def test_exile_lv0_keeps_doom(self, game):
        """放逐等级0手牌：不移除毁灭。"""
        inv = game.state.get_investigator("inv1")
        inv.resources = 5
        inv.hand = ["burn_after_reading_lv1", "lv0_card"]
        game.state.scenario.doom_on_agenda = 2

        game.action_resolver.perform_action(
            "inv1", Action.PLAY, card_id="burn_after_reading_lv1")
        assert "lv0_card" in game.state.scenario.vars["exiled_cards"]
        assert game.state.scenario.doom_on_agenda == 2
        assert inv.clues == 2
