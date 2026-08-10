"""Behavior tests for the guardian skill batch:
Daring (0), Defensive Stance (1).
"""

from backend.cards.guardian.daring_lv0 import Daring
from backend.cards.guardian.defensive_stance_lv1 import DefensiveStance
from backend.engine.game import Game
from backend.models.enums import ChaosTokenType, PlayerClass, Skill
from backend.tests.conftest import (
    make_investigator_data, make_location_data, make_skill_data,
)


def _game(willpower=3, intellect=3, combat=3, agility=3):
    g = Game("test")
    g.chaos_bag.seed(42)
    inv_data = make_investigator_data(
        willpower=willpower, intellect=intellect, combat=combat, agility=agility)
    g.register_card_data(inv_data)
    loc = make_location_data()
    g.register_card_data(loc)
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)
    return g


class TestDaring:
    def test_draw_after_test_when_committed(self):
        """投入后：3个任意图标生效；检定结束抽1张牌。"""
        g = _game(combat=3)
        g.register_card_data(make_skill_data(
            id="daring_lv0", card_class=PlayerClass.GUARDIAN,
            skill_icons={"wild": 3}))
        g.card_registry.register_class(Daring)
        inv = g.state.get_investigator("inv1")
        inv.hand = ["daring_lv0"]
        inv.deck = ["next_card"]
        g.chaos_bag.tokens = [ChaosTokenType.ZERO]
        result = g.skill_test_engine.run_test(
            "inv1", Skill.COMBAT, 6, committed_card_ids=["daring_lv0"])
        # 战斗3 + 3任意 = 6 vs 6 → 成功
        assert result.success is True
        assert result.committed_icons == 3
        assert "next_card" in inv.hand
        assert "daring_lv0" in inv.discard

    def test_no_draw_when_not_committed(self):
        """未投入的检定不触发抽牌。"""
        g = _game(combat=3)
        g.register_card_data(make_skill_data(
            id="daring_lv0", card_class=PlayerClass.GUARDIAN,
            skill_icons={"wild": 3}))
        g.card_registry.register_class(Daring)
        inv = g.state.get_investigator("inv1")
        inv.deck = ["next_card"]
        g.chaos_bag.tokens = [ChaosTokenType.ZERO]
        g.skill_test_engine.run_test("inv1", Skill.COMBAT, 2)
        assert inv.deck == ["next_card"]
        assert "next_card" not in inv.hand


class TestDefensiveStance:
    def _register(self, g):
        # make_skill_data 会把空 dict 默认为 {"wild": 1}，此处需要真空图标
        from backend.models.enums import CardType
        from backend.models.state import CardData
        g.register_card_data(CardData(
            id="defensive_stance_lv1", name="Defensive Stance", name_cn="防御姿态",
            type=CardType.SKILL, card_class=PlayerClass.GUARDIAN,
            skill_icons={}))
        g.card_registry.register_class(DefensiveStance)

    def test_combat_test_gains_agility_icons(self):
        """投入战斗检定：获得等同于敏捷(4)的战斗图标。"""
        g = _game(combat=3, agility=4)
        self._register(g)
        inv = g.state.get_investigator("inv1")
        inv.hand = ["defensive_stance_lv1"]
        g.chaos_bag.tokens = [ChaosTokenType.ZERO]
        result = g.skill_test_engine.run_test(
            "inv1", Skill.COMBAT, 7, committed_card_ids=["defensive_stance_lv1"])
        # 战斗3 + 敏捷4 = 7 vs 7 → 成功
        assert result.success is True
        assert result.committed_icons == 4

    def test_agility_test_gains_combat_icons(self):
        """投入敏捷检定：获得等同于战斗(3)的敏捷图标。"""
        g = _game(combat=3, agility=4)
        self._register(g)
        inv = g.state.get_investigator("inv1")
        inv.hand = ["defensive_stance_lv1"]
        g.chaos_bag.tokens = [ChaosTokenType.ZERO]
        result = g.skill_test_engine.run_test(
            "inv1", Skill.AGILITY, 7, committed_card_ids=["defensive_stance_lv1"])
        # 敏捷4 + 战斗3 = 7 vs 7 → 成功
        assert result.success is True
        assert result.committed_icons == 3

    def test_other_skill_no_icons(self):
        """投入其他技能检定：无图标加成。"""
        g = _game(combat=3, agility=4)
        self._register(g)
        inv = g.state.get_investigator("inv1")
        inv.hand = ["defensive_stance_lv1"]
        g.chaos_bag.tokens = [ChaosTokenType.ZERO]
        result = g.skill_test_engine.run_test(
            "inv1", Skill.WILLPOWER, 3,
            committed_card_ids=["defensive_stance_lv1"])
        assert result.committed_icons == 0
