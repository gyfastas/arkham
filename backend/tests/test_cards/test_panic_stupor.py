"""Tests for Panic & Stupor (Level 0) — action-type blocking basic weaknesses."""

from backend.cards.neutral.panic_lv0 import Panic
from backend.cards.neutral.stupor_lv0 import Stupor
from backend.engine.event_bus import EventContext
from backend.models.enums import Action, GameEvent


def _emit(game, event, inv_id="test_investigator", **kwargs):
    ctx = EventContext(game_state=game.state, event=event, investigator_id=inv_id, **kwargs)
    game.event_bus.emit(ctx)
    return ctx


def _draw(game, card_id, impl_cls):
    impl = impl_cls("weak_1")
    impl.register(game.event_bus, "weak_1")
    inv = game.state.get_investigator("test_investigator")
    inv.hand.append(card_id)
    _emit(game, GameEvent.CARD_DRAWN, extra={"card_id": card_id})
    return impl


def _threat_cards(game):
    inv = game.state.get_investigator("test_investigator")
    return [
        game.state.get_card_instance(iid).card_id
        for iid in inv.threat_area
        if game.state.get_card_instance(iid)
    ]


class TestPanic:
    def test_revelation_to_threat_area(self, game):
        _draw(game, "panic_lv0", Panic)
        assert "panic_lv0" in _threat_cards(game)

    def test_blocks_play_engage_resource_after_resource_action(self, game):
        """进行资源行动后：本回合封锁打出/交战/资源行动。"""
        impl = _draw(game, "panic_lv0", Panic)
        gs = game.state
        assert impl.can_take_action(gs, "test_investigator", Action.MOVE) is True

        _emit(game, GameEvent.ACTION_PERFORMED, action=Action.RESOURCE)
        assert impl.can_take_action(gs, "test_investigator", Action.RESOURCE) is False
        assert impl.can_take_action(gs, "test_investigator", Action.PLAY) is False
        assert impl.can_take_action(gs, "test_investigator", Action.ENGAGE) is False
        # 其他行动类型不封锁
        assert impl.can_take_action(gs, "test_investigator", Action.MOVE) is True
        assert impl.can_take_action(gs, "test_investigator", Action.FIGHT) is True

        # 回合结束解除
        _emit(game, GameEvent.INVESTIGATOR_TURN_ENDS)
        assert impl.can_take_action(gs, "test_investigator", Action.RESOURCE) is True

    def test_unrelated_action_does_not_block(self, game):
        impl = _draw(game, "panic_lv0", Panic)
        _emit(game, GameEvent.ACTION_PERFORMED, action=Action.FIGHT)
        assert impl.can_take_action(game.state, "test_investigator", Action.PLAY) is True

    def test_heal_discards(self, game):
        """视为1点恐惧治疗：丢弃恐慌。"""
        impl = _draw(game, "panic_lv0", Panic)
        inv = game.state.get_investigator("test_investigator")
        assert impl.heal(game.state, "test_investigator") is True
        assert "panic_lv0" not in _threat_cards(game)
        assert "panic_lv0" in inv.discard


class TestStupor:
    def test_revelation_to_threat_area(self, game):
        _draw(game, "stupor_lv0", Stupor)
        assert "stupor_lv0" in _threat_cards(game)

    def test_blocks_parley_draw_investigate(self, game):
        """进行调查行动后：本回合封锁谈判/抽牌/调查行动。"""
        impl = _draw(game, "stupor_lv0", Stupor)
        gs = game.state
        _emit(game, GameEvent.ACTION_PERFORMED, action=Action.INVESTIGATE)
        assert impl.can_take_action(gs, "test_investigator", Action.INVESTIGATE) is False
        assert impl.can_take_action(gs, "test_investigator", Action.DRAW) is False
        assert impl.can_take_action(gs, "test_investigator", Action.PARLEY) is False
        assert impl.can_take_action(gs, "test_investigator", Action.RESOURCE) is True

        _emit(game, GameEvent.INVESTIGATOR_TURN_ENDS)
        assert impl.can_take_action(gs, "test_investigator", Action.INVESTIGATE) is True

    def test_heal_discards(self, game):
        impl = _draw(game, "stupor_lv0", Stupor)
        inv = game.state.get_investigator("test_investigator")
        assert impl.heal(game.state, "test_investigator") is True
        assert "stupor_lv0" in inv.discard
