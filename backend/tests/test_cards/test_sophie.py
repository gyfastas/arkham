"""Tests for Sophie (Level 0) — Mark Harrigan signature asset."""

from backend.cards.neutral.sophie_lv0 import Sophie
from backend.models.enums import ChaosTokenType, Skill
from backend.models.state import CardInstance
from backend.tests.conftest import make_asset_data


def _setup(game):
    game.register_card_data(make_asset_data(id="sophie_lv0", cost=0))
    inv = game.state.get_investigator("test_investigator")
    inst = CardInstance(
        instance_id="so1", card_id="sophie_lv0",
        owner_id="test_investigator", controller_id="test_investigator",
    )
    game.state.cards_in_play["so1"] = inst
    inv.play_area.append("so1")
    impl = Sophie("so1")
    impl.register(game.event_bus, "so1")
    return impl, inv, inst


class TestSophie:
    def test_spend_gives_plus_2(self, game):
        """[fast]受1点直接伤害：本次检定+2（3+2=5 过难度4）。"""
        impl, inv, inst = _setup(game)
        assert impl.spend(game.state, "test_investigator") is True
        assert inv.damage == 1
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]
        result = game.skill_test_engine.run_test(
            "test_investigator", Skill.COMBAT, 4,
        )
        assert result.success
        assert result.modified_skill == 5

    def test_spend_stacks(self, game):
        """支付2次：+4。"""
        impl, inv, inst = _setup(game)
        impl.spend(game.state, "test_investigator")
        impl.spend(game.state, "test_investigator")
        assert inv.damage == 2
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]
        result = game.skill_test_engine.run_test(
            "test_investigator", Skill.COMBAT, 7,
        )
        assert result.success  # 3+4=7

    def test_flips_at_5_damage(self, game):
        """马克5点伤害 → 翻面；背面 spend 不可用且技能-1。"""
        impl, inv, inst = _setup(game)
        inv.damage = 4
        impl.spend(game.state, "test_investigator")  # 第5点伤害 → 翻面
        assert impl.check_flip(game.state, "test_investigator") is True
        assert impl.spend(game.state, "test_investigator") is False

        game.chaos_bag.tokens = [ChaosTokenType.ZERO]
        result = game.skill_test_engine.run_test(
            "test_investigator", Skill.COMBAT, 3,
        )
        assert not result.success  # 3-1=2 < 3

    def test_flip_on_assigned_damage(self, game):
        """经伤害分配达到5点同样翻面。"""
        impl, inv, inst = _setup(game)
        inv.damage = 3
        game.damage_engine.deal_damage("test_investigator", damage=2)
        assert inv.damage == 5
        assert impl.check_flip(game.state, "test_investigator") is True

    def test_flips_back_at_4_or_less(self, game):
        impl, inv, inst = _setup(game)
        inv.damage = 6
        impl.check_flip(game.state, "test_investigator")
        assert impl._flipped
        game.damage_engine.heal(investigator_id="test_investigator", damage=3)
        assert inv.damage == 3
        impl.check_flip(game.state, "test_investigator")
        assert not impl._flipped
