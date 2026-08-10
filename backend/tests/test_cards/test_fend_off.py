"""Tests for Fend Off (Level 3)."""

import pytest

from backend.cards.survivor.fend_off_lv3 import FendOff
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import GameEvent
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_enemy_data, make_event_data, make_investigator_data,
    make_location_data,
)


@pytest.fixture
def game():
    g = Game("test")
    inv_data = make_investigator_data(health=9, sanity=9)
    g.register_card_data(inv_data)
    loc = make_location_data()
    g.register_card_data(loc)
    g.register_card_data(make_event_data(
        id="fend_off_lv3", name="Fend Off", cost=2, fast=True))
    g.register_card_data(make_enemy_data(
        fight=3, health=3, evade=2, damage=2, horror=1))
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)
    g.card_registry.register_class(FendOff)
    g.card_registry.activate_card("fend_off_lv3", "impl_fend_off", g.event_bus)
    return g


class TestFendOff:
    def test_card_registered(self, game):
        assert "fend_off_lv3" in game.card_registry.registered_cards

    def test_resolve_attacks_then_auto_evades(self, game):
        """敌人生成时打出：敌人攻击你，然后被自动躲避且不能准备。"""
        inv = game.state.get_investigator("inv1")
        game.state.cards_in_play["enemy_1"] = CardInstance(
            instance_id="enemy_1", card_id="test_enemy",
            owner_id="scenario", controller_id="scenario",
        )
        inv.threat_area.append("enemy_1")

        impl = game.card_registry.active_instances["impl_fend_off"]
        assert impl.resolve(game.state, "inv1", "enemy_1") is True
        # 敌人攻击：2伤害1恐惧
        assert inv.damage == 2
        assert inv.horror == 1
        # 自动躲避：横置、脱离交战、留在地点
        enemy = game.state.get_card_instance("enemy_1")
        assert enemy.exhausted is True
        assert "enemy_1" not in inv.threat_area
        assert "enemy_1" in game.state.get_location("test_location").enemies
        # 叠加记录
        assert game.state.scenario.vars["fend_off_attached"]["enemy_1"] \
            == "fend_off_lv3"

    def test_attached_enemy_cannot_ready(self, game):
        """被叠加的敌人在准备后立即重新横置。"""
        inv = game.state.get_investigator("inv1")
        game.state.cards_in_play["enemy_1"] = CardInstance(
            instance_id="enemy_1", card_id="test_enemy",
            owner_id="scenario", controller_id="scenario",
        )
        inv.threat_area.append("enemy_1")
        impl = game.card_registry.active_instances["impl_fend_off"]
        impl.resolve(game.state, "inv1", "enemy_1")

        enemy = game.state.get_card_instance("enemy_1")
        enemy.exhausted = False  # 模拟 upkeep 准备
        game.event_bus.emit(EventContext(
            game_state=game.state, event=GameEvent.CARD_READIED,
            target="enemy_1"))
        assert enemy.exhausted is True
