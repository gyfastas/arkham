"""Tests for Interrogate (Level 0). (05020)

谈判。选择同地点类人生物敌人，检定战斗(3+X，X=敌人伤害值)；
成功则所在地点和另一地点各发现1条线索。
"""

import pytest
from backend.cards.guardian.interrogate_lv0 import Interrogate
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import GameEvent, PlayerClass
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_enemy_data, make_event_data, make_investigator_data,
    make_location_data,
)


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)
    inv_data = make_investigator_data(combat=4)
    g.register_card_data(inv_data)
    loc_a = make_location_data(id="loc_a", name="A", clue_value=2, connections=["loc_b"])
    loc_b = make_location_data(id="loc_b", name="B", clue_value=2, connections=["loc_a"])
    g.register_card_data(loc_a)
    g.register_card_data(loc_b)
    g.register_card_data(make_event_data(
        id="interrogate_lv0", name="Interrogate", cost=2,
        card_class=PlayerClass.GUARDIAN,
    ))
    g.register_card_data(make_enemy_data(
        id="cultist", name="Cultist", fight=2, health=2, evade=2, damage=2))
    g.state.card_database["cultist"].traits = ["humanoid"]
    g.register_card_data(make_enemy_data(
        id="monster", name="Monster", fight=2, health=2, evade=2, damage=1))
    g.state.card_database["monster"].traits = ["monster"]

    g.add_investigator("inv1", inv_data, starting_location="loc_a")
    g.add_location("loc_a", loc_a, clues=2)
    g.add_location("loc_b", loc_b, clues=1)
    g.card_registry.register_class(Interrogate)
    return g


def _play(game):
    impl = game.card_registry.activate_card(
        "interrogate_lv0", game.state.next_instance_id(), game.event_bus)
    ctx = EventContext(
        game_state=game.state, event=GameEvent.CARD_PLAYED,
        investigator_id="inv1", extra={"card_id": "interrogate_lv0"},
    )
    game.event_bus.emit(ctx)
    return ctx, impl


class TestInterrogate:
    def test_setup_and_success_discovers_2_clues(self, game):
        """难度=3+伤害值；成功后两个地点各发现1条线索。"""
        game.state.cards_in_play["enemy_1"] = CardInstance(
            instance_id="enemy_1", card_id="cultist",
            owner_id="scenario", controller_id="scenario",
        )
        game.state.get_investigator("inv1").threat_area.append("enemy_1")

        ctx, impl = _play(game)
        # X = 伤害值2 → 难度5
        assert ctx.extra["interrogate_difficulty"] == 5
        pending = game.state.scenario.vars["interrogate_test"]
        assert pending["enemy_instance_id"] == "enemy_1"

        inv = game.state.get_investigator("inv1")
        assert impl.on_test_result(game.state, True) is True
        assert game.state.get_location("loc_a").clues == 1  # 2→1
        assert game.state.get_location("loc_b").clues == 0  # 1→0
        assert inv.clues == 2

    def test_fizzle_without_humanoid(self, game):
        """同地点没有类人生物敌人：效果不结算。"""
        game.state.cards_in_play["enemy_1"] = CardInstance(
            instance_id="enemy_1", card_id="monster",
            owner_id="scenario", controller_id="scenario",
        )
        game.state.get_investigator("inv1").threat_area.append("enemy_1")

        ctx, impl = _play(game)
        assert ctx.extra["interrogate_fizzle"] is True
        assert "interrogate_test" not in game.state.scenario.vars

    def test_failure_no_clues(self, game):
        """检定失败：不发现线索。"""
        game.state.cards_in_play["enemy_1"] = CardInstance(
            instance_id="enemy_1", card_id="cultist",
            owner_id="scenario", controller_id="scenario",
        )
        game.state.get_investigator("inv1").threat_area.append("enemy_1")

        _, impl = _play(game)
        assert impl.on_test_result(game.state, False) is False
        assert game.state.get_location("loc_a").clues == 2
        assert game.state.get_location("loc_b").clues == 1
