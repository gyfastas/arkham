"""Tests for Forced Learning (Level 0)."""

import pytest
from backend.cards.seeker.forced_learning_lv0 import ForcedLearning
from backend.engine.game import Game
from backend.models.enums import PlayerClass
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_asset_data, make_investigator_data, make_location_data,
)


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)

    inv_data = make_investigator_data()
    g.register_card_data(inv_data)
    loc_data = make_location_data()
    g.register_card_data(loc_data)

    cheap = make_asset_data(id="cheap_card", name="Cheap", cost=1,
                            card_class=PlayerClass.SEEKER)
    pricey = make_asset_data(id="pricey_card", name="Pricey", cost=4,
                             card_class=PlayerClass.SEEKER)
    g.register_card_data(cheap)
    g.register_card_data(pricey)
    fl = make_asset_data(id="forced_learning_lv0", name="Forced Learning",
                         cost=0, card_class=PlayerClass.SEEKER)
    g.register_card_data(fl)

    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc_data, clues=0)

    # 支援卡入场（手工放置 + 注册实现）
    inst = CardInstance(
        instance_id="fl_1", card_id="forced_learning_lv0",
        owner_id="inv1", controller_id="inv1",
    )
    g.state.cards_in_play["fl_1"] = inst
    inv = g.state.get_investigator("inv1")
    inv.play_area.append("fl_1")
    impl = ForcedLearning("fl_1")
    impl.register(g.event_bus, "fl_1")
    return g


class TestForcedLearning:
    def test_upkeep_draw_two_discard_one(self, game):
        """补给阶段：改为抽2张并弃其中费用较低者。"""
        inv = game.state.get_investigator("inv1")
        inv.deck = ["cheap_card", "pricey_card", "rest_1", "rest_2"]
        inv.hand = []
        resources_before = inv.resources

        game.upkeep_phase.resolve()

        # 第1张 cheap（原 upkeep 抽牌）+ 补抽 pricey → 弃费用低的 cheap
        assert inv.hand == ["pricey_card"]
        assert inv.discard == ["cheap_card"]
        assert inv.resources == resources_before + 1  # upkeep 资源照常

    def test_non_upkeep_draws_untouched(self, game):
        """非补给阶段的抽牌不触发补抽/弃牌。"""
        from backend.engine.event_bus import EventContext
        from backend.models.enums import GameEvent, Phase

        inv = game.state.get_investigator("inv1")
        inv.deck = ["cheap_card", "pricey_card"]
        game.state.scenario.current_phase = Phase.INVESTIGATION
        game.event_bus.emit(EventContext(
            game_state=game.state, event=GameEvent.CARD_DRAWN,
            investigator_id="inv1", extra={"card_id": "cheap_card"},
        ))
        # 仅记录，不做补抽弃牌
        assert inv.deck == ["cheap_card", "pricey_card"]
        assert inv.discard == []

    def test_once_per_upkeep(self, game):
        """每个补给阶段只触发一次（后续 CARD_DRAWN 不再补抽）。"""
        from backend.engine.event_bus import EventContext
        from backend.models.enums import GameEvent, Phase

        inv = game.state.get_investigator("inv1")
        inv.deck = ["cheap_card", "pricey_card", "rest_1"]
        game.state.scenario.current_phase = Phase.UPKEEP
        game.event_bus.emit(EventContext(
            game_state=game.state, event=GameEvent.UPKEEP_PHASE_BEGINS,
        ))
        drawn = inv.deck.pop(0)  # 模拟引擎的 upkeep 抽牌
        inv.hand.append(drawn)
        game.event_bus.emit(EventContext(
            game_state=game.state, event=GameEvent.CARD_DRAWN,
            investigator_id="inv1", extra={"card_id": drawn},
        ))
        # 触发一次后：再发 CARD_DRAWN 不再补抽
        game.event_bus.emit(EventContext(
            game_state=game.state, event=GameEvent.CARD_DRAWN,
            investigator_id="inv1", extra={"card_id": "rest_1"},
        ))
        assert inv.deck == ["rest_1"]  # 只补抽过一次（pricey 被抽走）
        assert len(inv.discard) == 1
