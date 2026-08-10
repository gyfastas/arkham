"""Tests for Stick to the Plan (Level 3). (03264)

永久。卓越。[反应]抽取起始手牌前：从牌堆查找至多3张不同的策略/供给
事件卡叠加到本卡，洗牌。叠加卡可视为手牌打出；打出叠加卡的额外费用
是消耗（横置）本卡。
"""

import pytest
from backend.cards.guardian.stick_to_the_plan_lv3 import StickToThePlan, VAR
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import CardType, GameEvent, PlayerClass
from backend.models.state import CardData, CardInstance
from backend.tests.conftest import (
    make_investigator_data, make_location_data,
)


def _event(id, name, traits, cost=1):
    return CardData(
        id=id, name=name, name_cn=name, type=CardType.EVENT,
        card_class=PlayerClass.GUARDIAN, cost=cost, traits=traits,
    )


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)

    inv_data = make_investigator_data()
    g.register_card_data(inv_data)
    g.register_card_data(make_location_data())
    g.register_card_data(CardData(
        id="stick_to_the_plan_lv3", name="Stick to the Plan", name_cn="原定计划",
        type=CardType.ASSET, card_class=PlayerClass.GUARDIAN,
        traits=["talent"],
    ))
    g.register_card_data(_event("dynamite_blast_lv0", "Dynamite Blast", ["tactic"], cost=5))
    g.register_card_data(_event("taunt_lv0", "Taunt", ["tactic"], cost=1))
    g.register_card_data(_event("ever_vigilant_lv1", "Ever Vigilant", ["tactic"], cost=0))
    g.register_card_data(_event("emergency_cache_lv0", "Emergency Cache", [], cost=0))

    deck = [
        "emergency_cache_lv0", "dynamite_blast_lv0", "taunt_lv0",
        "ever_vigilant_lv1",
    ]
    g.add_investigator("inv1", inv_data, deck=deck, starting_location="test_location")
    g.add_location("test_location", g.state.get_card_data("test_location"), clues=2)
    g.card_registry.register_class(StickToThePlan)

    inv = g.state.get_investigator("inv1")
    inst = CardInstance(
        instance_id="sttp_1", card_id="stick_to_the_plan_lv3",
        owner_id="inv1", controller_id="inv1",
    )
    g.state.cards_in_play["sttp_1"] = inst
    inv.play_area.append("sttp_1")
    g.card_registry.activate_card("stick_to_the_plan_lv3", "sttp_1", g.event_bus)
    return g


def _enters_play(game):
    ctx = EventContext(
        game_state=game.state, event=GameEvent.CARD_ENTERS_PLAY,
        investigator_id="inv1", target="sttp_1",
        extra={"card_id": "stick_to_the_plan_lv3"},
    )
    game.event_bus.emit(ctx)


class TestStickToThePlan:
    def test_attaches_up_to_3_tactic_events_and_shuffles(self, game):
        """入场：3张策略事件被叠加并从牌堆移除，非策略卡留在牌堆。"""
        _enters_play(game)

        attached = game.state.scenario.vars[VAR]["inv1"]
        assert sorted(attached) == [
            "dynamite_blast_lv0", "ever_vigilant_lv1", "taunt_lv0",
        ]
        inv = game.state.get_investigator("inv1")
        assert inv.deck == ["emergency_cache_lv0"]  # 其余已移除并洗牌

    def test_setup_opening_idempotent(self, game):
        """重复触发不重复叠加。"""
        impl = game.card_registry.active_instances["sttp_1"]
        first = impl.setup_opening(game.state, "inv1")
        second = impl.setup_opening(game.state, "inv1")
        assert len(first) == 3
        assert second == []

    def test_play_attached_moves_to_hand_and_exhausts(self, game):
        """打出叠加卡：消耗（横置）原定计划，卡移入手牌。"""
        _enters_play(game)
        impl = game.card_registry.active_instances["sttp_1"]
        inv = game.state.get_investigator("inv1")
        inst = game.state.get_card_instance("sttp_1")

        assert impl.play_attached(game.state, "inv1", "taunt_lv0") is True
        assert "taunt_lv0" in inv.hand
        assert inst.exhausted is True
        assert "taunt_lv0" not in game.state.scenario.vars[VAR]["inv1"]

        # 已横置：不能再用
        assert impl.play_attached(game.state, "inv1", "dynamite_blast_lv0") is False
        assert "dynamite_blast_lv0" not in inv.hand

    def test_play_attached_rejects_unattached(self, game):
        """未叠加的卡不能经本卡打出。"""
        _enters_play(game)
        impl = game.card_registry.active_instances["sttp_1"]
        assert impl.play_attached(game.state, "inv1", "emergency_cache_lv0") is False
