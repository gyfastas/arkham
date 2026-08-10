"""Tests for On the Hunt (Level 0). (03263)

快速。神话阶段你将要抽遭遇卡时打出：改为在遭遇牌堆顶9张中找一个敌人，
生成并与你交战（代替其正常生成地点），混洗遭遇牌堆。
"""

import pytest
from backend.cards.guardian.on_the_hunt_lv0 import OnTheHunt
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import CardType, GameEvent, Phase, PlayerClass
from backend.models.state import CardData
from backend.tests.conftest import (
    make_enemy_data, make_event_data, make_investigator_data,
    make_location_data,
)


def _treachery(id):
    return CardData(
        id=id, name=id, name_cn=id, type=CardType.TREACHERY,
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
        id="on_the_hunt_lv0", name="On the Hunt", cost=1, fast=True,
        card_class=PlayerClass.GUARDIAN,
    ))
    g.register_card_data(_treachery("treachery_a"))
    g.register_card_data(_treachery("treachery_b"))
    g.register_card_data(make_enemy_data(
        id="wolf", name="Wolf", fight=3, health=3,
    ))

    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", g.state.get_card_data("test_location"), clues=2)
    g.card_registry.register_class(OnTheHunt)

    inv = g.state.get_investigator("inv1")
    inv.hand.append("on_the_hunt_lv0")
    inv.resources = 3
    g.card_registry.activate_card("on_the_hunt_lv0", "oth_1", g.event_bus)
    g.state.scenario.current_phase = Phase.MYTHOS
    return g


def _mythos_draw(game):
    """模拟 phase_mythos 的抽牌：弹出牌顶牌，发出事件，事件后入弃牌堆。"""
    scen = game.state.scenario
    drawn = scen.encounter_deck.pop(0)
    ctx = EventContext(
        game_state=game.state, event=GameEvent.ENCOUNTER_CARD_DRAWN,
        investigator_id="inv1", extra={"card_id": drawn},
    )
    game.event_bus.emit(ctx)
    scen.encounter_discard.append(drawn)  # 引擎无条件执行（见卡面 docstring）
    return ctx, drawn


class TestOnTheHunt:
    def test_searches_top_9_and_spawns_engaged(self, game):
        """顶9张内有敌人：自动打出，敌人生成并交战，牌堆混洗，原结算被取消。"""
        scen = game.state.scenario
        scen.encounter_deck = ["treachery_a", "wolf", "treachery_b"]
        inv = game.state.get_investigator("inv1")

        ctx, drawn = _mythos_draw(game)

        assert drawn == "treachery_a"
        assert ctx.cancelled is True  # 原遭遇结算被取消
        assert ctx.extra["on_the_hunt_spawned"] == "wolf"
        # 敌人生成并与持有者交战（不查其正常生成地点）
        spawned = [
            ci for ci in game.state.cards_in_play.values()
            if ci.card_id == "wolf"
        ]
        assert len(spawned) == 1
        assert spawned[0].instance_id in inv.threat_area
        # 狼已从牌堆移除，牌堆剩余1张（抽出1 + 生成1）
        assert "wolf" not in scen.encounter_deck
        assert len(scen.encounter_deck) == 1
        # 打出并付费
        assert "on_the_hunt_lv0" in inv.discard
        assert inv.resources == 2

    def test_no_enemy_in_top_9_draws_normally(self, game):
        """顶9张没有敌人：不打出，正常抽牌结算。"""
        scen = game.state.scenario
        scen.encounter_deck = ["treachery_a", "treachery_b"]
        inv = game.state.get_investigator("inv1")

        ctx, drawn = _mythos_draw(game)

        assert drawn == "treachery_a"
        assert ctx.cancelled is False
        assert "on_the_hunt_spawned" not in ctx.extra
        assert "on_the_hunt_lv0" in inv.hand  # 未打出
        assert inv.resources == 3
        assert scen.encounter_deck == ["treachery_b"]

    def test_not_triggered_outside_mythos(self, game):
        """非神话阶段抽遭遇卡不触发。"""
        game.state.scenario.current_phase = Phase.INVESTIGATION
        scen = game.state.scenario
        scen.encounter_deck = ["wolf", "treachery_a"]
        inv = game.state.get_investigator("inv1")

        ctx, drawn = _mythos_draw(game)
        assert ctx.cancelled is False
        assert "on_the_hunt_lv0" in inv.hand
