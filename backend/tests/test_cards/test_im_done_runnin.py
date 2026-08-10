"""Tests for "I'm done runnin'!" (Level 0)."""

import pytest
from backend.cards.neutral.im_done_runnin_lv0 import ImDoneRunnin
from backend.engine.game import Game
from backend.models.enums import Action, ChaosTokenType
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_enemy_data, make_event_data, make_investigator_data,
    make_location_data,
)


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)
    g.register_card_data(make_investigator_data(agility=5))
    g.register_card_data(make_location_data())
    g.register_card_data(make_event_data(
        id="im_done_runnin_lv0", name="I'm done runnin'!", fast=True,
    ))
    g.register_card_data(make_enemy_data(
        id="ghoul", name="Ghoul", fight=2, health=5, evade=2,
    ))
    g.add_investigator("inv1", g.state.get_card_data("test_investigator"),
                       starting_location="test_location")
    g.add_location("test_location", g.state.get_card_data("test_location"))
    g.card_registry.register_class(ImDoneRunnin)
    inv = g.state.get_investigator("inv1")
    inv.hand.append("im_done_runnin_lv0")
    inv.resources = 5
    g.chaos_bag.tokens = [ChaosTokenType.ZERO]

    enemy = CardInstance(
        instance_id="enemy_1", card_id="ghoul",
        owner_id="scenario", controller_id="scenario",
        exhausted=True,  # 横置的未交战敌人
    )
    g.state.cards_in_play["enemy_1"] = enemy
    g.state.get_location("test_location").enemies.append("enemy_1")
    return g


class TestImDoneRunnin:
    def test_ready_and_engage_then_evade_deals_damage(self, game):
        """打出：准备并交战同地点敌人；本回合躲避对其造成1伤害。"""
        inv = game.state.get_investigator("inv1")
        game.action_resolver.perform_action(
            "inv1", Action.PLAY, card_id="im_done_runnin_lv0",
        )
        enemy = game.state.get_card_instance("enemy_1")
        assert "enemy_1" in inv.threat_area
        assert enemy.exhausted is False

        ok = game.action_resolver.perform_action(
            "inv1", Action.EVADE, enemy_instance_id="enemy_1",
        )
        assert ok is True
        assert enemy.damage == 1  # 躲避造成1点伤害

    def test_evade_damage_only_during_that_turn(self, game):
        """回合结束后躲避不再造成伤害。"""
        inv = game.state.get_investigator("inv1")
        game.action_resolver.perform_action(
            "inv1", Action.PLAY, card_id="im_done_runnin_lv0",
        )
        # 回合结束
        from backend.engine.event_bus import EventContext
        from backend.models.enums import GameEvent
        game.event_bus.emit(EventContext(
            game_state=game.state, event=GameEvent.INVESTIGATOR_TURN_ENDS,
            investigator_id="inv1",
        ))
        game.action_resolver.perform_action(
            "inv1", Action.EVADE, enemy_instance_id="enemy_1",
        )
        enemy = game.state.get_card_instance("enemy_1")
        assert enemy.damage == 0
