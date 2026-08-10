"""Tests for Gate Box (Level 0)."""

import pytest
from backend.cards.neutral.gate_box_lv0 import GateBox
from backend.engine.game import Game
from backend.models.enums import Action
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_asset_data, make_enemy_data, make_investigator_data,
    make_location_data,
)


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)
    g.register_card_data(make_investigator_data())
    g.register_card_data(make_location_data())
    # 数据 JSON 中 uses 键为 "chargess"（上游笔误），测试兼容路径
    g.register_card_data(make_asset_data(
        id="gate_box_lv0", name="Gate Box", cost=3, uses={"chargess": 3},
    ))
    g.register_card_data(make_enemy_data(id="ghoul", name="Ghoul"))
    g.register_card_data(make_location_data(
        id="dream_gate_wondrous_journey", name="Dream-Gate",
    ))
    g.add_investigator("inv1", g.state.get_card_data("test_investigator"),
                       starting_location="test_location")
    g.add_location("test_location", g.state.get_card_data("test_location"))
    g.add_location("dream_gate_wondrous_journey",
                   g.state.get_card_data("dream_gate_wondrous_journey"))
    g.card_registry.register_class(GateBox)
    inv = g.state.get_investigator("inv1")
    inv.hand.append("gate_box_lv0")
    inv.resources = 5
    return g


def _play(game):
    game.action_resolver.perform_action(
        "inv1", Action.PLAY, card_id="gate_box_lv0",
    )
    return next(
        i for i in game.card_registry.active_instances.values()
        if isinstance(i, GateBox)
    )


def _engage_enemy(game):
    enemy = CardInstance(
        instance_id="enemy_1", card_id="ghoul",
        owner_id="scenario", controller_id="scenario",
    )
    game.state.cards_in_play["enemy_1"] = enemy
    game.state.get_investigator("inv1").threat_area.append("enemy_1")
    return enemy


class TestGateBox:
    def test_disengage_and_spend_charge(self, game):
        """横置+1充能：脱离所有交战敌人。"""
        impl = _play(game)
        _engage_enemy(game)
        inv = game.state.get_investigator("inv1")

        assert impl.activate(game.state, "inv1") is True
        inst = game.state.get_card_instance(impl.instance_id)
        assert inst.exhausted is True
        assert inst.uses["chargess"] == 2
        assert inv.threat_area == []
        assert "enemy_1" in game.state.get_location("test_location").enemies

    def test_move_to_bonded_dream_gate(self, game):
        """绑定卡中有梦境之门且已在场上：移动过去。"""
        impl = _play(game)
        game.state.scenario.vars["bonded"] = {
            "inv1": ["dream_gate_wondrous_journey"],
        }
        assert impl.activate(game.state, "inv1") is True
        inv = game.state.get_investigator("inv1")
        assert inv.location_id == "dream_gate_wondrous_journey"
