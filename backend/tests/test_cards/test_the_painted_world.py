"""Tests for The Painted World (Level 0) — Sefina Rousseau signature event."""

from backend.cards.neutral.the_painted_world_lv0 import ThePaintedWorld
from backend.engine.event_bus import EventContext
from backend.models.enums import GameEvent
from backend.tests.conftest import make_asset_data, make_event_data


def _play(game, beneath):
    ThePaintedWorld("p1").register(game.event_bus, "p1")
    inv = game.state.get_investigator("test_investigator")
    game.state.scenario.vars["beneath_test_investigator"] = list(beneath)
    ctx = EventContext(
        game_state=game.state, event=GameEvent.CARD_PLAYED,
        investigator_id="test_investigator",
        extra={"card_id": "the_painted_world_lv0"},
    )
    game.event_bus.emit(ctx)
    return ctx, inv


class TestThePaintedWorld:
    def test_copies_event_beneath_and_removed_from_game(self, game):
        """复制赛菲娜下的第一张事件；本卡移出游戏而非弃掉。"""
        game.register_card_data(make_event_data(id="event_x"))
        game.register_card_data(make_asset_data(id="asset_y"))
        ctx, inv = _play(game, beneath=["asset_y", "event_x"])

        assert ctx.extra["painted_world_copy"] == "event_x"
        assert ctx.extra["painted_world_removed"] is True
        removed = game.state.scenario.vars["removed_from_game"]
        assert "the_painted_world_lv0" in removed
        # 被复制的事件仍留在赛菲娜下
        assert game.state.scenario.vars["beneath_test_investigator"] == ["asset_y", "event_x"]
        assert "the_painted_world_lv0" not in inv.discard

    def test_no_event_beneath_still_removed(self, game):
        """赛菲娜下无事件：无复制目标，但仍移出游戏。"""
        ctx, inv = _play(game, beneath=[])
        assert ctx.extra["painted_world_copy"] is None
        assert "the_painted_world_lv0" in game.state.scenario.vars["removed_from_game"]

    def test_explicit_copy_choice(self, game):
        """会话层可经 extra.copy_card_id 指定复制目标。"""
        game.register_card_data(make_event_data(id="event_a"))
        game.register_card_data(make_event_data(id="event_b"))
        ThePaintedWorld("p2").register(game.event_bus, "p2")
        inv = game.state.get_investigator("test_investigator")
        game.state.scenario.vars["beneath_test_investigator"] = ["event_a", "event_b"]
        ctx = EventContext(
            game_state=game.state, event=GameEvent.CARD_PLAYED,
            investigator_id="test_investigator",
            extra={"card_id": "the_painted_world_lv0", "copy_card_id": "event_b"},
        )
        game.event_bus.emit(ctx)
        assert ctx.extra["painted_world_copy"] == "event_b"
