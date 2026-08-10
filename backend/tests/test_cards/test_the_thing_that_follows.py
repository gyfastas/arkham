"""Tests for The Thing That Follows (Level 0) — Neutral basic weakness enemy."""

from backend.cards.neutral.the_thing_that_follows_lv0 import TheThingThatFollows
from backend.models.state import CardInstance
from backend.tests.conftest import make_enemy_data


def _setup(game):
    TheThingThatFollows("t1").register(game.event_bus, "t1")
    game.register_card_data(make_enemy_data(
        id="the_thing_that_follows_lv0", fight=3, health=2, evade=3,
        keywords=["hunter"],
    ))
    inv = game.state.get_investigator("test_investigator")
    inv.deck = ["d1", "d2", "d3"]
    thing = CardInstance(
        instance_id="th1", card_id="the_thing_that_follows_lv0",
        owner_id="test_investigator", controller_id="scenario",
    )
    game.state.cards_in_play["th1"] = thing
    inv.threat_area.append("th1")
    return inv, thing


class TestTheThingThatFollows:
    def test_defeat_shuffles_into_bearer_deck(self, game):
        """将要被击败时：改为洗入承受者牌组（不进遭遇弃牌堆/胜利牌区）。"""
        inv, thing = _setup(game)
        game.damage_engine.deal_damage_to_enemy(
            "th1", 2, investigator_id="test_investigator",
        )
        assert "th1" not in game.state.cards_in_play
        assert "th1" not in inv.threat_area
        assert "the_thing_that_follows_lv0" in inv.deck
        assert len(inv.deck) == 4
        assert "the_thing_that_follows_lv0" not in game.state.scenario.encounter_discard
        assert game.state.scenario.victory_display == []

    def test_other_enemy_defeat_unaffected(self, game):
        """其他敌人被击败不触发。"""
        inv, thing = _setup(game)
        game.register_card_data(make_enemy_data(id="rat", health=1))
        rat = CardInstance(
            instance_id="r1", card_id="rat",
            owner_id="scenario", controller_id="scenario",
        )
        game.state.cards_in_play["r1"] = rat
        inv.threat_area.append("r1")
        game.damage_engine.deal_damage_to_enemy(
            "r1", 1, investigator_id="test_investigator",
        )
        assert "r1" not in game.state.cards_in_play
        assert "th1" in game.state.cards_in_play  # 鬼影仍在场
        assert len(inv.deck) == 3
