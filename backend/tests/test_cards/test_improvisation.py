"""Tests for Improvisation (Level 0) — Lola Hayes signature event."""

from backend.cards.neutral.improvisation_lv0 import Improvisation
from backend.engine.event_bus import EventContext
from backend.models.enums import GameEvent, PlayerClass
from backend.tests.conftest import make_asset_data


def _play(game, new_role="guardian"):
    Improvisation("i1").register(game.event_bus, "i1")
    inv = game.state.get_investigator("test_investigator")
    inv.deck = ["d1", "d2"]
    ctx = EventContext(
        game_state=game.state, event=GameEvent.CARD_PLAYED,
        investigator_id="test_investigator",
        extra={"card_id": "improvisation_lv0", "new_role": new_role},
    )
    game.event_bus.emit(ctx)
    return ctx, inv


class TestImprovisation:
    def test_switches_role_arms_discount_draws(self, game):
        ctx, inv = _play(game, new_role="guardian")
        vars = game.state.scenario.vars
        assert vars["role_test_investigator"] == "guardian"
        assert vars["improvisation_discount_test_investigator"] == 3
        assert inv.hand == ["d1"]
        assert ctx.extra["improvisation_role"] == "guardian"

    def test_cost_discount_applies_to_role_card_once(self, game):
        ctx, inv = _play(game, new_role="guardian")
        game.register_card_data(make_asset_data(
            id="guard_card", card_class=PlayerClass.GUARDIAN))
        game.register_card_data(make_asset_data(
            id="seeker_card", card_class=PlayerClass.SEEKER))

        impl = Improvisation("i2")
        # 非角色卡无折扣，且不清除
        assert impl.get_cost_discount(game.state, "test_investigator", "seeker_card") == 0
        # 角色卡折扣3，首次使用后清除
        assert impl.get_cost_discount(game.state, "test_investigator", "guard_card") == 3
        assert impl.get_cost_discount(game.state, "test_investigator", "guard_card") == 0

    def test_discount_expires_at_turn_end(self, game):
        ctx, inv = _play(game)
        impl = Improvisation("i3")
        turn_end = EventContext(
            game_state=game.state, event=GameEvent.INVESTIGATOR_TURN_ENDS,
            investigator_id="test_investigator",
        )
        game.event_bus.emit(turn_end)
        game.register_card_data(make_asset_data(
            id="guard_card", card_class=PlayerClass.GUARDIAN))
        assert impl.get_cost_discount(game.state, "test_investigator", "guard_card") == 0
