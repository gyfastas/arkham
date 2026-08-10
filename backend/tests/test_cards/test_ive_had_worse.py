"""Tests for "I've had worse..." (Level 4)."""

import pytest
from backend.cards.guardian.ive_had_worse_lv4 import IveHadWorse
from backend.engine.event_bus import EventContext
from backend.models.enums import GameEvent


@pytest.fixture
def worse_game(game):
    impl = IveHadWorse("impl_1")
    impl.register(game.event_bus, "impl_1")
    inv = game.state.get_investigator("test_investigator")
    inv.hand = ["ive_had_worse_lv4"]
    inv.resources = 2
    return game


def _emit(game, event, amount, **kwargs):
    ctx = EventContext(
        game_state=game.state, event=event,
        investigator_id="test_investigator", amount=amount, **kwargs
    )
    game.event_bus.emit(ctx)
    return ctx


class TestIveHadWorse:
    def test_card_id(self):
        assert IveHadWorse.card_id == "ive_had_worse_lv4"

    def test_cancels_up_to_5_damage_and_gains_resources(self, worse_game):
        """受到3点伤害：自动打出，取消3点，获得3资源（费用0）。"""
        game = worse_game
        inv = game.state.get_investigator("test_investigator")

        ctx = _emit(game, GameEvent.DAMAGE_ASSIGNED, 3)
        assert ctx.amount == 0
        assert ctx.extra["ive_had_worse_cancelled"] == 3
        assert "ive_had_worse_lv4" not in inv.hand
        assert "ive_had_worse_lv4" in inv.discard
        assert inv.resources == 2 + 3  # 费用0，+3资源

    def test_cancel_capped_at_5(self, worse_game):
        """至多取消5点：7点伤害取消5点，获得5资源。"""
        game = worse_game
        inv = game.state.get_investigator("test_investigator")

        ctx = _emit(game, GameEvent.DAMAGE_ASSIGNED, 7)
        assert ctx.amount == 2
        assert ctx.extra["ive_had_worse_cancelled"] == 5
        assert inv.resources == 2 + 5

    def test_cancels_horror(self, worse_game):
        """恐惧同样触发取消。"""
        game = worse_game
        inv = game.state.get_investigator("test_investigator")

        ctx = _emit(game, GameEvent.HORROR_ASSIGNED, 2)
        assert ctx.amount == 0
        assert ctx.extra["ive_had_worse_cancelled"] == 2
        assert inv.resources == 2 + 2

    def test_no_trigger_without_card_in_hand(self, worse_game):
        """手牌没有本卡时不触发。"""
        game = worse_game
        inv = game.state.get_investigator("test_investigator")
        inv.hand = []

        ctx = _emit(game, GameEvent.DAMAGE_ASSIGNED, 3)
        assert ctx.amount == 3
        assert "ive_had_worse_cancelled" not in ctx.extra
        assert inv.resources == 2

    def test_no_trigger_on_enemy_damage(self, worse_game):
        """旧行为（对敌人造成伤害时误触发）已移除：DAMAGE_DEALT 不触发。"""
        game = worse_game
        inv = game.state.get_investigator("test_investigator")

        ctx = _emit(game, GameEvent.DAMAGE_DEALT, 5)
        assert ctx.amount == 5
        assert "ive_had_worse_lv4" in inv.hand
        assert inv.resources == 2
