"""Tests for Siren Call (Level 0)."""

from backend.cards.neutral.siren_call_lv0 import SirenCall
from backend.engine.event_bus import EventContext
from backend.models.enums import GameEvent, Skill
from backend.tests.conftest import make_skill_data


def _draw(game):
    impl = SirenCall("siren_1")
    impl.register(game.event_bus, "siren_1")
    inv = game.state.get_investigator("test_investigator")
    inv.hand.append("siren_call_lv0")
    game.event_bus.emit(EventContext(
        game_state=game.state, event=GameEvent.CARD_DRAWN,
        investigator_id="test_investigator",
        extra={"card_id": "siren_call_lv0"},
    ))
    return impl


def _commit(game, cards, skill=Skill.WILLPOWER):
    ctx = EventContext(
        game_state=game.state, event=GameEvent.SKILL_TEST_COMMIT,
        investigator_id="test_investigator", skill_type=skill,
        committed_cards=cards, amount=0,
    )
    game.event_bus.emit(ctx)
    return ctx


class TestSirenCall:
    def test_revelation_to_threat_area(self, game):
        _draw(game)
        inv = game.state.get_investigator("test_investigator")
        inst = game.state.get_card_instance(inv.threat_area[0])
        assert inst.card_id == "siren_call_lv0"

    def test_surcharge_auto_collected(self, game):
        """投入带匹配图标的卡牌：按图标数扣资源。"""
        _draw(game)
        # 2个意志图标 + 1个wild → 意志检定匹配3个图标
        game.register_card_data(make_skill_data(
            id="guts_lv0", skill_icons={"willpower": 2, "wild": 1}))
        inv = game.state.get_investigator("test_investigator")
        inv.resources = 5

        ctx = _commit(game, ["guts_lv0"], Skill.WILLPOWER)
        assert inv.resources == 2  # 5 - 3
        assert ctx.extra["siren_call_surcharge"] == 3

    def test_non_matching_icons_free(self, game):
        """无匹配图标：不扣资源。"""
        _draw(game)
        game.register_card_data(make_skill_data(
            id="overpower_lv0", skill_icons={"combat": 2}))
        inv = game.state.get_investigator("test_investigator")
        inv.resources = 5

        ctx = _commit(game, ["overpower_lv0"], Skill.WILLPOWER)
        assert inv.resources == 5
        assert "siren_call_surcharge" not in ctx.extra

    def test_unpaid_when_poor(self, game):
        """资源不足：标记欠费（会话层应阻止投入）。"""
        _draw(game)
        game.register_card_data(make_skill_data(
            id="guts_lv0", skill_icons={"willpower": 2}))
        inv = game.state.get_investigator("test_investigator")
        inv.resources = 1

        ctx = _commit(game, ["guts_lv0"], Skill.WILLPOWER)
        assert inv.resources == 1
        assert ctx.extra["siren_call_unpaid"] == 2

    def test_discard_activation(self, game):
        impl = _draw(game)
        inv = game.state.get_investigator("test_investigator")
        assert impl.activate_discard(game.state, "test_investigator") is True
        assert "siren_call_lv0" in inv.discard
