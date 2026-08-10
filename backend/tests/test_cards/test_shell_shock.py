"""Tests for Shell Shock (Level 0) — Mark Harrigan signature weakness."""

from backend.cards.neutral.shell_shock_lv0 import ShellShock
from backend.engine.event_bus import EventContext
from backend.models.enums import GameEvent


def _draw(game, inv_id="test_investigator"):
    ctx = EventContext(
        game_state=game.state, event=GameEvent.CARD_DRAWN,
        investigator_id=inv_id, extra={"card_id": "shell_shock_lv0"},
    )
    game.event_bus.emit(ctx)
    return ctx


class TestShellShock:
    def test_revelation_horror_half_damage(self, game):
        """身上4点伤害 → 受到2点恐惧，卡入弃牌堆。"""
        ShellShock("s1").register(game.event_bus, "s1")
        inv = game.state.get_investigator("test_investigator")
        inv.hand.append("shell_shock_lv0")
        inv.damage = 4

        ctx = _draw(game)
        assert inv.horror == 2
        assert ctx.extra["shell_shock_horror"] == 2
        assert "shell_shock_lv0" not in inv.hand
        assert "shell_shock_lv0" in inv.discard

    def test_rounds_down(self, game):
        """3点伤害 → 1点恐惧（每2点伤害1点恐惧）。"""
        ShellShock("s1").register(game.event_bus, "s1")
        inv = game.state.get_investigator("test_investigator")
        inv.hand.append("shell_shock_lv0")
        inv.damage = 3

        _draw(game)
        assert inv.horror == 1

    def test_no_damage_no_horror(self, game):
        ShellShock("s1").register(game.event_bus, "s1")
        inv = game.state.get_investigator("test_investigator")
        inv.hand.append("shell_shock_lv0")

        _draw(game)
        assert inv.horror == 0
        assert "shell_shock_lv0" in inv.discard

    def test_ignores_other_cards(self, game):
        ShellShock("s1").register(game.event_bus, "s1")
        inv = game.state.get_investigator("test_investigator")
        inv.damage = 6
        ctx = EventContext(
            game_state=game.state, event=GameEvent.CARD_DRAWN,
            investigator_id="test_investigator", extra={"card_id": "guts_lv0"},
        )
        game.event_bus.emit(ctx)
        assert inv.horror == 0
