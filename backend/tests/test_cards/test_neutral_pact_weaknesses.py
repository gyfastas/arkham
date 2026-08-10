"""Tests for The Price of Failure and Voice of the Messenger (Pact weaknesses)."""

import pytest

from backend.cards.neutral.the_price_of_failure_lv0 import ThePriceOfFailure
from backend.cards.neutral.voice_of_the_messenger_lv0 import VoiceOfTheMessenger
from backend.engine.event_bus import EventContext
from backend.models.enums import GameEvent


def _emit(game, event, inv_id="test_investigator", **kwargs):
    ctx = EventContext(
        game_state=game.state, event=event, investigator_id=inv_id, **kwargs
    )
    game.event_bus.emit(ctx)
    return ctx


def _register(game, impl_cls, instance_id="weakness_impl"):
    impl = impl_cls(instance_id)
    impl.register(game.event_bus, instance_id)
    return impl


def _draw(game, card_id, inv_id="test_investigator"):
    inv = game.state.get_investigator(inv_id)
    inv.hand.append(card_id)
    return _emit(game, GameEvent.CARD_DRAWN, inv_id, extra={"card_id": card_id})


class TestThePriceOfFailure:
    def test_revelation_full_effect(self, game):
        """显现：2伤害+2恐惧、密谋+1毁灭、移出游戏、黑暗契约入弃牌堆。"""
        _register(game, ThePriceOfFailure)
        inv = game.state.get_investigator("test_investigator")
        doom_before = game.state.scenario.doom_on_agenda

        ctx = _draw(game, "the_price_of_failure_lv0")

        assert inv.damage == 2
        assert inv.horror == 2
        assert game.state.scenario.doom_on_agenda == doom_before + 1
        assert "the_price_of_failure_lv0" not in inv.hand
        assert "the_price_of_failure_lv0" in game.state.scenario.vars[
            "removed_from_game"]
        assert "dark_pact_lv0" in inv.discard
        assert ctx.extra.get("price_of_failure_resolved") is True

    def test_doom_can_advance_agenda(self, game):
        """放置的毁灭可导致当前密谋推进。"""
        _register(game, ThePriceOfFailure)
        game.state.scenario.doom_threshold = 1
        idx = game.state.scenario.current_agenda_index
        _draw(game, "the_price_of_failure_lv0")
        assert game.state.scenario.current_agenda_index == idx + 1
        assert game.state.scenario.doom_on_agenda == 0  # 推进后清空


class TestVoiceOfTheMessenger:
    def test_revelation_default_choice_damage(self, game):
        """未预选时自动选择：1直接伤害+1肉体创伤，随后进入弃牌堆。"""
        _register(game, VoiceOfTheMessenger)
        inv = game.state.get_investigator("test_investigator")

        ctx = _draw(game, "voice_of_the_messenger_lv0")

        assert inv.damage == 1
        assert inv.horror == 0
        assert getattr(inv, "physical_trauma", 0) == 1
        assert game.state.scenario.vars["trauma"]["test_investigator"][
            "physical"] == 1
        assert "voice_of_the_messenger_lv0" not in inv.hand
        assert "voice_of_the_messenger_lv0" in inv.discard
        assert ctx.extra.get("voice_of_the_messenger_choice") == "damage"

    def test_revelation_preset_choice_horror(self, game):
        """会话层预选 horror：1直接恐惧+1精神创伤。"""
        _register(game, VoiceOfTheMessenger)
        game.state.scenario.vars["voice_of_the_messenger_choice"] = {
            "test_investigator": "horror"}
        inv = game.state.get_investigator("test_investigator")

        _draw(game, "voice_of_the_messenger_lv0")

        assert inv.horror == 1
        assert inv.damage == 0
        assert getattr(inv, "mental_trauma", 0) == 1
        assert game.state.scenario.vars["trauma"]["test_investigator"][
            "mental"] == 1

    def test_resolve_choice_rejects_invalid(self, game):
        impl = _register(game, VoiceOfTheMessenger)
        assert impl.resolve_choice(game.state, "test_investigator", "bad") is False
