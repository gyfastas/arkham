"""Tests for Rookie Mistake (Level 0)."""

from backend.cards.neutral.rookie_mistake_lv0 import RookieMistake
from backend.engine.event_bus import EventContext
from backend.models.enums import CardType, GameEvent
from backend.models.state import CardInstance
from backend.tests.conftest import make_asset_data


def _draw(game):
    impl = RookieMistake("rm_1")
    impl.register(game.event_bus, "rm_1")
    inv = game.state.get_investigator("test_investigator")
    inv.hand.append("rookie_mistake_lv0")
    ctx = EventContext(
        game_state=game.state, event=GameEvent.CARD_DRAWN,
        investigator_id="test_investigator",
        extra={"card_id": "rookie_mistake_lv0"},
    )
    game.event_bus.emit(ctx)
    return ctx


def _add_asset(game, instance_id, damage=0, horror=0):
    data = make_asset_data(id=f"asset_{instance_id}", health=3, sanity=3)
    game.register_card_data(data)
    ci = CardInstance(
        instance_id=instance_id, card_id=data.id,
        owner_id="test_investigator", controller_id="test_investigator",
    )
    ci.damage = damage
    ci.horror = horror
    game.state.cards_in_play[instance_id] = ci
    game.state.get_investigator("test_investigator").play_area.append(instance_id)
    return ci


class TestRookieMistake:
    def test_discards_damaged_assets(self, game):
        """显现：丢弃所有带伤害/恐惧的支援卡，自身入弃牌堆。"""
        _add_asset(game, "a1", damage=1)
        _add_asset(game, "a2", horror=2)
        _add_asset(game, "a3")  # 无伤害恐惧，保留
        inv = game.state.get_investigator("test_investigator")

        ctx = _draw(game)
        assert set(ctx.extra["rookie_mistake_discarded"]) == {f"asset_a1", f"asset_a2"}
        assert "a1" not in inv.play_area
        assert "a2" not in inv.play_area
        assert "a3" in inv.play_area
        assert "rookie_mistake_lv0" in inv.discard

    def test_shuffles_back_when_nothing_discarded(self, game):
        """无支援被丢弃：洗回牌组。"""
        _add_asset(game, "a3")
        inv = game.state.get_investigator("test_investigator")
        deck_before = len(inv.deck)

        ctx = _draw(game)
        assert ctx.extra["rookie_mistake_discarded"] == []
        assert "rookie_mistake_lv0" not in inv.discard
        assert "rookie_mistake_lv0" in inv.deck
        assert len(inv.deck) == deck_before + 1
        assert "rookie_mistake_lv0" not in inv.hand
