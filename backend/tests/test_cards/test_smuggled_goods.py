"""Tests for Smuggled Goods (Level 0)."""

from backend.cards.neutral.smuggled_goods_lv0 import SmuggledGoods
from backend.engine.event_bus import EventContext
from backend.models.enums import CardType, GameEvent, PlayerClass
from backend.models.state import CardData, CardInstance
from backend.tests.conftest import make_enemy_data


def _register(game):
    impl = SmuggledGoods("sg_1")
    impl.register(game.event_bus, "sg_1")
    return impl


def _illicit(game, card_id="liquid_courage_lv0"):
    game.register_card_data(CardData(
        id=card_id, name=card_id, name_cn=card_id,
        type=CardType.ASSET, card_class=PlayerClass.NEUTRAL,
        cost=1, traits=["illicit"],
    ))
    return card_id


def _play(game):
    ctx = EventContext(
        game_state=game.state, event=GameEvent.CARD_PLAYED,
        investigator_id="test_investigator",
        extra={"card_id": "smuggled_goods_lv0"},
    )
    game.event_bus.emit(ctx)
    return ctx


class TestSmuggledGoods:
    def test_search_discard_pile(self, game):
        """弃牌堆有违禁品：抽取之。"""
        _register(game)
        cid = _illicit(game)
        inv = game.state.get_investigator("test_investigator")
        inv.discard = [cid]

        ctx = _play(game)
        assert ctx.extra["smuggled_goods_found"] == cid
        assert ctx.extra["smuggled_goods_searched_deck"] is False
        assert cid in inv.hand
        assert cid not in inv.discard

    def test_search_deck_top_nine(self, game):
        """弃牌堆没有：检索牌堆顶9张；之后洗回走私货物。"""
        impl = _register(game)
        cid = _illicit(game)
        inv = game.state.get_investigator("test_investigator")
        inv.deck = ["x1", "x2", cid, "x4"]

        ctx = _play(game)
        assert ctx.extra["smuggled_goods_found"] == cid
        assert ctx.extra["smuggled_goods_searched_deck"] is True
        assert cid in inv.hand
        assert cid not in inv.deck

        # 引擎结算后事件入弃牌堆 → 会话层调用洗回
        inv.discard.append("smuggled_goods_lv0")
        assert impl.resolve_shuffle_back(game.state, "test_investigator") is True
        assert "smuggled_goods_lv0" in inv.deck
        assert "smuggled_goods_lv0" not in inv.discard

    def test_fizzles_with_ready_enemy(self, game):
        """同地点有就绪敌人：效果不发动。"""
        _register(game)
        cid = _illicit(game)
        game.register_card_data(make_enemy_data())
        enemy = CardInstance(
            instance_id="enemy_1", card_id="test_enemy",
            owner_id="scenario", controller_id="scenario",
        )
        game.state.cards_in_play["enemy_1"] = enemy
        inv = game.state.get_investigator("test_investigator")
        inv.threat_area.append("enemy_1")
        inv.discard = [cid]

        ctx = _play(game)
        assert ctx.extra["smuggled_goods_fizzled"] is True
        assert cid in inv.discard
        assert cid not in inv.hand

    def test_no_illicit_found(self, game):
        """找不到违禁品：无事发生。"""
        _register(game)
        inv = game.state.get_investigator("test_investigator")
        inv.deck = ["x1", "x2"]
        ctx = _play(game)
        assert ctx.extra["smuggled_goods_found"] is None
        assert inv.hand == []
