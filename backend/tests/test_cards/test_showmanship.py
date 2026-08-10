"""Tests for Showmanship (Level 0)."""

from backend.cards.neutral.showmanship_lv0 import Showmanship
from backend.engine.event_bus import EventContext
from backend.models.enums import GameEvent, Skill
from backend.models.state import CardInstance
from backend.tests.conftest import make_asset_data


def _equip(game):
    inv = game.state.get_investigator("test_investigator")
    ci = CardInstance(
        instance_id="show_1", card_id="showmanship_lv0",
        owner_id="test_investigator", controller_id="test_investigator",
    )
    game.state.cards_in_play["show_1"] = ci
    inv.play_area.append("show_1")
    impl = Showmanship("show_1")
    impl.register(game.event_bus, "show_1")
    return impl


def _enters(game, card_id, instance_id):
    ctx = EventContext(
        game_state=game.state, event=GameEvent.CARD_ENTERS_PLAY,
        investigator_id="test_investigator", target=instance_id,
        extra={"card_id": card_id},
    )
    game.event_bus.emit(ctx)
    return ctx


def _skill_ctx(game, source, amount=3):
    ctx = EventContext(
        game_state=game.state, event=GameEvent.SKILL_VALUE_DETERMINED,
        investigator_id="test_investigator", skill_type=Skill.COMBAT,
        amount=amount, source=source,
    )
    game.event_bus.emit(ctx)
    return ctx


class TestShowmanship:
    def test_boost_on_tracked_asset_ability(self, game):
        """支援进场后：结算其触发能力时技能+2，直到回合结束。"""
        _equip(game)
        game.register_card_data(make_asset_data(id="shrivelling_lv0"))
        _enters(game, "shrivelling_lv0", "shriv_1")

        ctx = _skill_ctx(game, "shriv_1", amount=3)
        assert ctx.amount == 5  # +2

    def test_no_boost_for_other_sources(self, game):
        """其他来源的检定无加值。"""
        _equip(game)
        game.register_card_data(make_asset_data(id="shrivelling_lv0"))
        _enters(game, "shrivelling_lv0", "shriv_1")

        ctx = _skill_ctx(game, "machete_1", amount=3)
        assert ctx.amount == 3

    def test_expires_at_round_end(self, game):
        """回合结束后加值失效。"""
        _equip(game)
        game.register_card_data(make_asset_data(id="shrivelling_lv0"))
        _enters(game, "shrivelling_lv0", "shriv_1")
        game.event_bus.emit(EventContext(
            game_state=game.state, event=GameEvent.ROUND_ENDS,
            investigator_id="test_investigator",
        ))
        ctx = _skill_ctx(game, "shriv_1", amount=3)
        assert ctx.amount == 3
