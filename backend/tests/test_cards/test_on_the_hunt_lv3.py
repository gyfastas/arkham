"""Tests for On the Hunt (Level 3). (08028)

快速。神话阶段将抽遭遇卡时打出：改为从整个遭遇牌堆查找一个敌人生成、
与你交战并叠加本卡；你击败被叠加敌人时获得3资源。
"""

import pytest
from backend.cards.guardian.on_the_hunt_lv3 import OnTheHuntLv3
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import CardType, GameEvent, Phase, PlayerClass
from backend.models.state import CardData
from backend.tests.conftest import (
    make_enemy_data, make_event_data, make_investigator_data,
    make_location_data,
)


def _treachery(cid):
    return CardData(
        id=cid, name=cid, name_cn=cid, type=CardType.TREACHERY,
        card_class=PlayerClass.NEUTRAL,
    )


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)
    inv_data = make_investigator_data()
    g.register_card_data(inv_data)
    g.register_card_data(make_location_data())
    g.register_card_data(make_event_data(
        id="on_the_hunt_lv3", name="On the Hunt", cost=0, fast=True,
        card_class=PlayerClass.GUARDIAN,
    ))
    g.register_card_data(_treachery("treachery_a"))
    g.register_card_data(make_enemy_data(id="wolf", name="Wolf", fight=3, health=2))

    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", g.state.get_card_data("test_location"), clues=0)
    g.card_registry.register_class(OnTheHuntLv3)

    inv = g.state.get_investigator("inv1")
    inv.hand.append("on_the_hunt_lv3")
    g.card_registry.activate_card("on_the_hunt_lv3", "oth3_1", g.event_bus)
    g.state.scenario.current_phase = Phase.MYTHOS
    return g


def _mythos_draw(game):
    scen = game.state.scenario
    drawn = scen.encounter_deck.pop(0)
    ctx = EventContext(
        game_state=game.state, event=GameEvent.ENCOUNTER_CARD_DRAWN,
        investigator_id="inv1", extra={"card_id": drawn},
    )
    game.event_bus.emit(ctx)
    scen.encounter_discard.append(drawn)
    return ctx, drawn


class TestOnTheHuntLv3:
    def test_searches_whole_deck_and_spawns(self, game):
        """敌人不在牌顶：仍被找出（全牌堆查找），生成并交战，叠加记录。"""
        scen = game.state.scenario
        # 敌人放在第10张以后——lv0 的顶9张找不到，lv3 能找整个牌堆
        scen.encounter_deck = ["treachery_a"] * 10 + ["wolf", "treachery_a"]
        inv = game.state.get_investigator("inv1")

        ctx, drawn = _mythos_draw(game)

        assert ctx.cancelled is True
        assert ctx.extra["on_the_hunt_spawned"] == "wolf"
        spawned = [
            ci for ci in game.state.cards_in_play.values()
            if ci.card_id == "wolf"
        ]
        assert len(spawned) == 1
        assert spawned[0].instance_id in inv.threat_area
        assert game.state.scenario.vars["on_the_hunt_lv3"][
            spawned[0].instance_id] == "inv1"
        assert "wolf" not in scen.encounter_deck
        assert "on_the_hunt_lv3" in inv.discard

    def test_bounty_on_defeat(self, game):
        """击败被叠加敌人：获得3资源。"""
        scen = game.state.scenario
        scen.encounter_deck = ["treachery_a", "wolf"]
        inv = game.state.get_investigator("inv1")
        inv.resources = 1

        _mythos_draw(game)
        spawned = next(
            ci for ci in game.state.cards_in_play.values()
            if ci.card_id == "wolf"
        )
        # 持有者击败它
        game.damage_engine.deal_damage_to_enemy(
            spawned.instance_id, 2, investigator_id="inv1")

        assert inv.resources == 4  # 1 + 3
        assert game.state.scenario.vars["on_the_hunt_lv3"] == {}

    def test_no_bounty_when_other_defeats(self, game):
        """其他调查员击败被叠加敌人：无奖励。"""
        scen = game.state.scenario
        scen.encounter_deck = ["treachery_a", "wolf"]
        inv = game.state.get_investigator("inv1")
        inv.resources = 1

        _mythos_draw(game)
        spawned = next(
            ci for ci in game.state.cards_in_play.values()
            if ci.card_id == "wolf"
        )
        game.damage_engine.deal_damage_to_enemy(
            spawned.instance_id, 2, investigator_id="someone_else")

        assert inv.resources == 1
