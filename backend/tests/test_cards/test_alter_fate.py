"""Tests for Alter Fate (Level 3)."""

import pytest

from backend.cards.survivor.alter_fate_lv3 import AlterFate
from backend.engine.game import Game
from backend.models.enums import Action, CardType, PlayerClass
from backend.models.state import CardData, CardInstance
from backend.tests.conftest import (
    make_event_data, make_investigator_data, make_location_data,
)


def make_treachery_data(id="test_treachery", subtype=""):
    return CardData(
        id=id, name="Test Treachery", name_cn="测试诡计",
        type=CardType.TREACHERY, card_class=PlayerClass.MYSTIC,
        subtype=subtype,
    )


@pytest.fixture
def game():
    g = Game("test")
    inv_data = make_investigator_data()
    g.register_card_data(inv_data)
    loc = make_location_data()
    g.register_card_data(loc)
    g.register_card_data(make_event_data(
        id="alter_fate_lv3", name="Alter Fate", cost=1, fast=True))
    g.register_card_data(make_treachery_data())
    g.register_card_data(make_treachery_data(
        id="test_weakness_treachery", subtype="weakness"))
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)
    g.card_registry.register_class(AlterFate)
    return g


class TestAlterFate:
    def test_card_registered(self, game):
        assert "alter_fate_lv3" in game.card_registry.registered_cards

    def test_discards_treachery_in_threat_area(self, game):
        """打出：丢弃威胁区中的非弱点诡计卡（场景卡进遭遇弃牌堆）。"""
        inv = game.state.get_investigator("inv1")
        inv.resources = 5
        inv.hand = ["alter_fate_lv3"]
        game.state.cards_in_play["treachery_1"] = CardInstance(
            instance_id="treachery_1", card_id="test_treachery",
            owner_id="scenario", controller_id="scenario",
        )
        inv.threat_area.append("treachery_1")

        assert game.action_resolver.perform_action(
            "inv1", Action.PLAY, card_id="alter_fate_lv3") is True
        assert "treachery_1" not in inv.threat_area
        assert "treachery_1" not in game.state.cards_in_play
        assert "test_treachery" in game.state.scenario.encounter_discard
        assert inv.resources == 4

    def test_ignores_weakness_treachery(self, game):
        """弱点诡计卡不是合法目标。"""
        inv = game.state.get_investigator("inv1")
        inv.resources = 5
        inv.hand = ["alter_fate_lv3"]
        game.state.cards_in_play["weakness_1"] = CardInstance(
            instance_id="weakness_1", card_id="test_weakness_treachery",
            owner_id="inv1", controller_id="inv1",
        )
        inv.threat_area.append("weakness_1")

        assert game.action_resolver.perform_action(
            "inv1", Action.PLAY, card_id="alter_fate_lv3") is True
        assert "weakness_1" in inv.threat_area
