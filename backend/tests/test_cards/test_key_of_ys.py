"""Tests for Key of Ys (Level 5) — Neutral asset."""

from backend.cards.neutral.key_of_ys_lv5 import KeyOfYs
from backend.engine.event_bus import EventContext
from backend.models.enums import ChaosTokenType, GameEvent, Skill
from backend.models.state import CardInstance
from backend.tests.conftest import make_asset_data


def _setup(game, horror=0):
    game.register_card_data(make_asset_data(id="key_of_ys_lv5", sanity=4))
    inv = game.state.get_investigator("test_investigator")
    inst = CardInstance(
        instance_id="key1", card_id="key_of_ys_lv5",
        owner_id="test_investigator", controller_id="test_investigator",
        horror=horror,
    )
    game.state.cards_in_play["key1"] = inst
    inv.play_area.append("key1")
    impl = KeyOfYs("key1")
    impl.register(game.event_bus, "key1")
    return impl, inv, inst


class TestKeyOfYs:
    def test_skill_boost_per_horror(self, game):
        """钥匙上2点恐惧：技能+2（3基础+2=5 过难度4）。"""
        impl, inv, inst = _setup(game, horror=2)
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]
        result = game.skill_test_engine.run_test(
            "test_investigator", Skill.WILLPOWER, 4,
        )
        assert result.success
        assert result.modified_skill == 5

    def test_no_horror_no_boost(self, game):
        impl, inv, inst = _setup(game, horror=0)
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]
        result = game.skill_test_engine.run_test(
            "test_investigator", Skill.WILLPOWER, 4,
        )
        assert not result.success  # 3 vs 4

    def test_horror_redirected_to_key(self, game):
        """2点恐惧分配：1点到钥匙，调查员只受1点。"""
        impl, inv, inst = _setup(game, horror=0)
        game.damage_engine.deal_damage("test_investigator", horror=2)
        assert inst.horror == 1
        assert inv.horror == 1

    def test_leaves_play_discards_top_10(self, game):
        """离场：弃牌堆顶10张。"""
        impl, inv, inst = _setup(game, horror=0)
        inv.deck = [f"c{i}" for i in range(12)]
        # 模拟引擎移出场上（如资产战败后的离场事件）
        inv.play_area.remove("key1")
        game.state.cards_in_play.pop("key1")
        ctx = EventContext(
            game_state=game.state, event=GameEvent.CARD_LEAVES_PLAY,
            investigator_id="test_investigator", target="key1",
            extra={"card_id": "key_of_ys_lv5"},
        )
        game.event_bus.emit(ctx)
        assert len(inv.discard) == 10
        assert len(inv.deck) == 2

    def test_defeat_by_redirected_horror_triggers_leaves_play(self, game):
        """重定向的恐惧把钥匙撑爆（恐惧≥理智4）：离场并弃牌堆顶10张。"""
        impl, inv, inst = _setup(game, horror=3)
        inv.deck = [f"c{i}" for i in range(11)]
        game.damage_engine.deal_damage("test_investigator", horror=1)
        assert "key1" not in game.state.cards_in_play
        assert "key_of_ys_lv5" in inv.discard
        assert len(inv.discard) == 11  # 钥匙本体 + 10张牌
        assert inv.horror == 0  # 那1点恐惧被钥匙吸收
