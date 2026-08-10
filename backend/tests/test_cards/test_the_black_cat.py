"""Tests for The Black Cat (Level 5)."""

from backend.cards.neutral.the_black_cat_lv5 import TheBlackCat
from backend.engine.event_bus import EventContext
from backend.models.enums import ChaosTokenType, GameEvent, Skill
from backend.models.state import CardData, CardInstance
from backend.models.enums import CardType, PlayerClass


def _equip(game, damage=0, horror=0):
    game.register_card_data(CardData(
        id="the_black_cat_lv5", name="The Black Cat", name_cn="黑猫",
        type=CardType.ASSET, card_class=PlayerClass.NEUTRAL, cost=2,
        traits=["ally", "avatar", "dreamlands"], health=3, sanity=3,
    ))
    inv = game.state.get_investigator("test_investigator")
    ci = CardInstance(
        instance_id="cat_1", card_id="the_black_cat_lv5",
        owner_id="test_investigator", controller_id="test_investigator",
    )
    ci.damage = damage
    ci.horror = horror
    game.state.cards_in_play["cat_1"] = ci
    inv.play_area.append("cat_1")
    impl = TheBlackCat("cat_1")
    impl.register(game.event_bus, "cat_1")
    return impl, ci


def _token_ctx(game, token, amount=0):
    ctx = EventContext(
        game_state=game.state, event=GameEvent.CHAOS_TOKEN_RESOLVED,
        investigator_id="test_investigator", skill_type=Skill.WILLPOWER,
        chaos_token=token, amount=amount,
    )
    game.event_bus.emit(ctx)
    return ctx


class TestTheBlackCat:
    def test_tablet_replaced(self, game):
        """[石板]：-1，黑猫受1直接伤害。"""
        _, ci = _equip(game)
        ctx = _token_ctx(game, ChaosTokenType.TABLET, amount=0)
        assert ctx.amount == -1
        assert ci.damage == 1
        assert ctx.extra["black_cat_replaced"] == "tablet"

    def test_elder_thing_replaced(self, game):
        """[古神]：-1，黑猫受1直接恐惧。"""
        _, ci = _equip(game)
        ctx = _token_ctx(game, ChaosTokenType.ELDER_THING, amount=0)
        assert ctx.amount == -1
        assert ci.horror == 1
        assert ctx.extra["black_cat_replaced"] == "elder_thing"

    def test_elder_sign_heals_and_plus_five(self, game):
        """[远古印记]：+5，治疗黑猫全部伤害恐惧。"""
        _, ci = _equip(game, damage=2, horror=1)
        ctx = _token_ctx(game, ChaosTokenType.ELDER_SIGN, amount=0)
        assert ctx.amount == 5
        assert ci.damage == 0 and ci.horror == 0
        assert ctx.extra["black_cat_replaced"] == "elder_sign"

    def test_suicidal_replacement_skipped(self, game):
        """替换会致黑猫被击败时不替换（自动选择）。"""
        _, ci = _equip(game, damage=2)  # 生命3：再受1伤即败
        ctx = _token_ctx(game, ChaosTokenType.TABLET, amount=0)
        assert ctx.amount == 0
        assert ci.damage == 2
        assert "black_cat_replaced" not in ctx.extra

    def test_unrelated_token_untouched(self, game):
        """其他标记不受影响。"""
        _, ci = _equip(game)
        ctx = _token_ctx(game, ChaosTokenType.SKULL, amount=-2)
        assert ctx.amount == -2
        assert ci.damage == 0
