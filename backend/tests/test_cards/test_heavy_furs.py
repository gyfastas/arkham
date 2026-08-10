"""Tests for Heavy Furs (Level 0)."""

import pytest
from backend.cards.neutral.heavy_furs_lv0 import HeavyFurs
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import Action, ChaosTokenType, GameEvent, Skill
from backend.tests.conftest import (
    make_asset_data, make_investigator_data, make_location_data,
)


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)
    g.register_card_data(make_investigator_data())
    g.register_card_data(make_location_data())
    g.register_card_data(make_asset_data(
        id="heavy_furs_lv0", name="Heavy Furs", cost=2, health=2,
    ))
    g.add_investigator("inv1", g.state.get_card_data("test_investigator"),
                       starting_location="test_location")
    g.add_location("test_location", g.state.get_card_data("test_location"))
    g.card_registry.register_class(HeavyFurs)
    inv = g.state.get_investigator("inv1")
    inv.hand.append("heavy_furs_lv0")
    inv.resources = 5
    return g


def _play(game):
    game.action_resolver.perform_action(
        "inv1", Action.PLAY, card_id="heavy_furs_lv0",
    )
    return next(
        i for i in game.card_registry.active_instances.values()
        if isinstance(i, HeavyFurs)
    )


class TestHeavyFurs:
    def test_cancel_symbol_and_redraw(self, game):
        """武装后揭示符号标记：取消并按新揭示标记（+1）结算。"""
        impl = _play(game)
        assert impl.activate(game.state, "inv1") is True
        inst = game.state.get_card_instance(impl.instance_id)
        assert inst.damage == 1  # 费用：对毛皮造成1点伤害

        # 重抽固定为 +1
        game.chaos_bag.tokens = [ChaosTokenType.PLUS_1]
        ctx = EventContext(
            game_state=game.state, event=GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="inv1", chaos_token=ChaosTokenType.SKULL,
            amount=-2, skill_type=Skill.COMBAT,
        )
        game.event_bus.emit(ctx)
        assert ctx.amount == 1  # -2 被取消，替换为 +1

    def test_not_triggered_by_numeric_token(self, game):
        """数字标记不触发（保持武装）。"""
        impl = _play(game)
        impl.activate(game.state, "inv1")
        game.chaos_bag.tokens = [ChaosTokenType.PLUS_1]
        ctx = EventContext(
            game_state=game.state, event=GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="inv1", chaos_token=ChaosTokenType.MINUS_3,
            amount=-3, skill_type=Skill.COMBAT,
        )
        game.event_bus.emit(ctx)
        assert ctx.amount == -3
        assert impl._armed is True

    def test_full_test_flow(self, game):
        """完整检定流程：袋中仅 skull（修正视为0），取消后重抽仍为 skull。"""
        impl = _play(game)
        impl.activate(game.state, "inv1")
        game.chaos_bag.tokens = [ChaosTokenType.SKULL]
        result = game.skill_test_engine.run_test("inv1", Skill.COMBAT, 3)
        assert result.token_modifier == 0
