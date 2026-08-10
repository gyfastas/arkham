"""Tests for Evidence! (Level 0)."""

from backend.cards.guardian.evidence_lv0 import Evidence
from backend.engine.event_bus import EventContext
from backend.models.enums import GameEvent


def _play(game, card_id, inv_id="test_investigator", **extra):
    ctx = EventContext(
        game_state=game.state, event=GameEvent.CARD_PLAYED,
        investigator_id=inv_id, extra={"card_id": card_id, **extra},
    )
    game.event_bus.emit(ctx)
    return ctx


class TestEvidence:
    def test_card_id(self):
        assert Evidence.card_id == "evidence_lv0"

    def test_discovers_clue_on_play(self, game):
        """打出证据：发现所在地点1条线索。"""
        impl = Evidence("impl_1")
        impl.register(game.event_bus, "impl_1")
        inv = game.state.get_investigator("test_investigator")
        loc = game.state.locations["test_location"]
        assert loc.clues == 3
        inv.clues = 0

        ctx = _play(game, "evidence_lv0")
        assert loc.clues == 2
        assert inv.clues == 1
        assert ctx.extra["evidence_clue_discovered"] is True

    def test_ignores_other_cards(self, game):
        """其他卡打出时不触发。"""
        impl = Evidence("impl_1")
        impl.register(game.event_bus, "impl_1")
        loc = game.state.locations["test_location"]

        _play(game, "dynamite_blast_lv0")
        assert loc.clues == 3

    def test_no_clues_no_effect(self, game):
        """地点没有线索时不报错、不欠费。"""
        impl = Evidence("impl_1")
        impl.register(game.event_bus, "impl_1")
        inv = game.state.get_investigator("test_investigator")
        loc = game.state.locations["test_location"]
        loc.clues = 0
        inv.clues = 0

        ctx = _play(game, "evidence_lv0")
        assert inv.clues == 0
        assert "evidence_clue_discovered" not in ctx.extra

    def test_enemy_defeated_does_not_trigger(self, game):
        """旧行为（监听 ENEMY_DEFEATED）已移除：击败敌人本身不发现线索。"""
        impl = Evidence("impl_1")
        impl.register(game.event_bus, "impl_1")
        loc = game.state.locations["test_location"]

        ctx = EventContext(
            game_state=game.state, event=GameEvent.ENEMY_DEFEATED,
            investigator_id="test_investigator", target="enemy_1",
            extra={"card_id": "test_enemy"},
        )
        game.event_bus.emit(ctx)
        assert loc.clues == 3
