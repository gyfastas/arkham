"""Tests for Scene of the Crime (Level 0) and Second Wind (Level 0). (04103/04149)

犯罪现场：首行动打出，发现1线索（地点有敌人则2），不引起趁乱攻击。
恢复元气：首行动打出，治愈1伤害（本轮抽过诡计则2），抽1张牌。
"""

import pytest

from backend.cards.guardian.scene_of_the_crime_lv0 import SceneOfTheCrime
from backend.cards.guardian.second_wind_lv0 import SecondWind
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import (
    Action, CardType, GameEvent, PlayerClass,
)
from backend.models.state import CardData, CardInstance
from backend.tests.conftest import (
    make_enemy_data, make_event_data, make_investigator_data,
    make_location_data,
)


def _game():
    g = Game("test")
    g.chaos_bag.seed(42)
    inv_data = make_investigator_data()
    g.register_card_data(inv_data)
    loc = make_location_data(clue_value=3)
    g.register_card_data(loc)
    g.register_card_data(make_event_data(
        id="scene_of_the_crime_lv0", name="Scene of the Crime", cost=2,
        card_class=PlayerClass.GUARDIAN,
    ))
    g.register_card_data(make_event_data(
        id="second_wind_lv0", name="Second Wind", cost=1,
        card_class=PlayerClass.GUARDIAN,
    ))
    g.register_card_data(make_enemy_data(id="ghoul", damage=1, horror=1))
    g.register_card_data(CardData(
        id="rotting_remains", name="Rotting Remains", name_cn="腐尸残骸",
        type=CardType.TREACHERY, card_class=PlayerClass.NEUTRAL,
        traits=["hazard"],
    ))
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", g.state.get_card_data("test_location"), clues=3)
    g.card_registry.register_class(SceneOfTheCrime)
    g.card_registry.register_class(SecondWind)
    inv = g.state.get_investigator("inv1")
    inv.actions_remaining = 3
    return g


def _spawn_engaged(game):
    enemy = CardInstance(
        instance_id="enemy_1", card_id="ghoul",
        owner_id="scenario", controller_id="scenario",
    )
    game.state.cards_in_play["enemy_1"] = enemy
    game.state.get_investigator("inv1").threat_area.append("enemy_1")
    return enemy


class TestSceneOfTheCrime:
    def test_first_action_two_clues_with_enemy(self):
        """首行动打出且地点有敌人（交战中）：发现2线索，且不引起趁乱攻击。"""
        game = _game()
        _spawn_engaged(game)
        inv = game.state.get_investigator("inv1")
        inv.hand.append("scene_of_the_crime_lv0")
        loc = game.state.locations["test_location"]

        ok = game.action_resolver.perform_action(
            "inv1", Action.PLAY, card_id="scene_of_the_crime_lv0",
        )
        assert ok is True
        assert inv.clues == 2
        assert loc.clues == 1
        # AoO 被豁免：未受敌人攻击伤害/恐惧
        assert inv.damage == 0 and inv.horror == 0

    def test_first_action_one_clue_without_enemy(self):
        """地点无敌人：发现1线索。"""
        game = _game()
        inv = game.state.get_investigator("inv1")
        inv.hand.append("scene_of_the_crime_lv0")
        loc = game.state.locations["test_location"]

        game.action_resolver.perform_action(
            "inv1", Action.PLAY, card_id="scene_of_the_crime_lv0",
        )
        assert inv.clues == 1
        assert loc.clues == 2

    def test_not_first_action_fizzles(self):
        """已行动过（剩余<3）：不发现线索。"""
        game = _game()
        inv = game.state.get_investigator("inv1")
        inv.hand.append("scene_of_the_crime_lv0")
        inv.actions_remaining = 2

        game.action_resolver.perform_action(
            "inv1", Action.PLAY, card_id="scene_of_the_crime_lv0",
        )
        assert inv.clues == 0


class TestSecondWind:
    def test_heal_1_and_draw(self):
        """首行动打出：治愈1伤害，抽1张牌。"""
        game = _game()
        inv = game.state.get_investigator("inv1")
        inv.hand.append("second_wind_lv0")
        inv.damage = 2
        inv.deck = ["some_card"]

        game.action_resolver.perform_action(
            "inv1", Action.PLAY, card_id="second_wind_lv0",
        )
        assert inv.damage == 1
        assert "some_card" in inv.hand

    def test_heal_2_after_treachery_drawn(self):
        """本轮抽过诡计卡：治愈2伤害。"""
        game = _game()
        inv = game.state.get_investigator("inv1")
        inv.hand.append("second_wind_lv0")
        inv.damage = 3
        inv.deck = ["some_card"]

        # 模拟手牌持续实例（跟踪本轮诡计抽取）
        tracker = SecondWind("sw_hand")
        tracker.register(game.event_bus, "sw_hand")
        game.event_bus.emit(EventContext(
            game_state=game.state, event=GameEvent.ENCOUNTER_CARD_DRAWN,
            investigator_id="inv1", extra={"card_id": "rotting_remains"},
        ))

        game.action_resolver.perform_action(
            "inv1", Action.PLAY, card_id="second_wind_lv0",
        )
        assert inv.damage == 1  # 治愈2点
        assert "some_card" in inv.hand
