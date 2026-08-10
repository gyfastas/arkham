"""Tests for The Codex of Ages (Level 0)."""

from backend.cards.neutral.the_codex_of_ages_lv0 import TheCodexOfAges
from backend.engine.event_bus import EventContext
from backend.models.chaos import ChaosBag
from backend.models.enums import ChaosTokenType, GameEvent, Skill
from backend.models.state import CardInstance


def _equip(game, tokens):
    bag = ChaosBag(tokens=list(tokens))
    bag.seed(1)
    inv = game.state.get_investigator("test_investigator")
    ci = CardInstance(
        instance_id="codex_1", card_id="the_codex_of_ages_lv0",
        owner_id="test_investigator", controller_id="test_investigator",
    )
    game.state.cards_in_play["codex_1"] = ci
    inv.play_area.append("codex_1")
    impl = TheCodexOfAges("codex_1")
    impl.register(game.event_bus, "codex_1")
    impl.bind_chaos_bag(bag)
    # 进场事件 → 封印
    game.event_bus.emit(EventContext(
        game_state=game.state, event=GameEvent.CARD_ENTERS_PLAY,
        investigator_id="test_investigator", target="codex_1",
        extra={"card_id": "the_codex_of_ages_lv0"},
    ))
    return impl, bag


class TestTheCodexOfAges:
    def test_seals_elder_sign_on_enter(self, game):
        """进场：封印[远古印记]。"""
        impl, bag = _equip(game, [ChaosTokenType.ELDER_SIGN, ChaosTokenType.SKULL])
        assert ChaosTokenType.ELDER_SIGN in bag.sealed
        inst = game.state.get_card_instance("codex_1")
        assert inst.uses["sealed_elder_sign"] == 1

    def test_willpower_bonus_while_sealed(self, game):
        """有标记封印时：+1意志。"""
        _equip(game, [ChaosTokenType.ELDER_SIGN])
        ctx = EventContext(
            game_state=game.state, event=GameEvent.SKILL_VALUE_DETERMINED,
            investigator_id="test_investigator", skill_type=Skill.WILLPOWER,
            amount=3,
        )
        game.event_bus.emit(ctx)
        assert ctx.amount == 4

    def test_resolve_sealed_elder_sign(self, game):
        """反应：丢弃古抄，下一次揭示改为结算[远古印记]。"""
        impl, bag = _equip(game, [ChaosTokenType.ELDER_SIGN])
        inv = game.state.get_investigator("test_investigator")

        assert impl.activate_sealed(game.state, "test_investigator") is True
        # 古抄已弃置
        assert game.state.get_card_instance("codex_1") is None
        assert "the_codex_of_ages_lv0" in inv.discard

        # 下一次标记揭示被改写
        ctx = EventContext(
            game_state=game.state, event=GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="test_investigator", skill_type=Skill.COMBAT,
            chaos_token=ChaosTokenType.SKULL, amount=0,
        )
        game.event_bus.emit(ctx)
        assert ctx.chaos_token == ChaosTokenType.ELDER_SIGN
        assert ctx.extra["codex_of_ages_elder_sign"] is True
        # 封印的标记结算后释回袋中
        assert ChaosTokenType.ELDER_SIGN in bag.tokens
        assert ChaosTokenType.ELDER_SIGN not in bag.sealed

    def test_activate_requires_sealed_token(self, game):
        """无封印标记时不能发动反应。"""
        impl, bag = _equip(game, [ChaosTokenType.SKULL])  # 袋中无远古印记可封
        assert impl.activate_sealed(game.state, "test_investigator") is False
