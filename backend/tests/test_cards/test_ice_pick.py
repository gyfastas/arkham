"""Tests for Ice Pick (Level 1 & Level 3)."""

import pytest
from backend.cards.seeker.ice_pick_lv1 import IcePick
from backend.cards.seeker.ice_pick_lv3 import IcePickLv3
from backend.engine.game import Game
from backend.models.chaos import ChaosBag
from backend.models.enums import Action, ChaosTokenType
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_asset_data, make_enemy_data, make_investigator_data,
    make_location_data,
)


def _build_game(card_id, impl_cls, combat=3, intellect=3, fight=4, shroud=3):
    g = Game("test")
    g.chaos_bag = ChaosBag()
    g.chaos_bag.seed(42)
    g.skill_test_engine.chaos_bag = g.chaos_bag

    inv_data = make_investigator_data(combat=combat, intellect=intellect)
    g.register_card_data(inv_data)
    loc_data = make_location_data(shroud=shroud)
    g.register_card_data(loc_data)
    enemy_data = make_enemy_data(fight=fight, health=20)
    g.register_card_data(enemy_data)
    g.register_card_data(make_asset_data(id=card_id, cost=1))

    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc_data, clues=3)

    enemy = CardInstance(
        instance_id="e1", card_id="test_enemy",
        owner_id="scenario", controller_id="scenario",
    )
    g.state.cards_in_play["e1"] = enemy
    inv = g.state.get_investigator("inv1")
    inv.threat_area.append("e1")
    inv.actions_remaining = 3

    inst = CardInstance(
        instance_id="pick_1", card_id=card_id,
        owner_id="inv1", controller_id="inv1",
    )
    g.state.cards_in_play["pick_1"] = inst
    inv.play_area.append("pick_1")
    impl = impl_cls("pick_1")
    impl.register(g.event_bus, "pick_1")
    return g, inv, enemy, inst, impl


class TestIcePickLv1:
    def test_fight_bonus_turns_miss_into_hit(self):
        """战斗力3对4：武装后+1命中。"""
        g, inv, enemy, inst, impl = _build_game("ice_pick_lv1", IcePick)
        g.chaos_bag.tokens = [ChaosTokenType.ZERO]

        assert impl.use(g.state, "inv1") is True
        ok = g.action_resolver.perform_action(
            "inv1", Action.FIGHT, enemy_instance_id="e1")
        assert ok is True
        assert enemy.damage == 1  # 3+1=4 对难度4命中
        assert inst.exhausted is True

    def test_bonus_not_applied_to_other_skills(self):
        """武装后的非攻击/调查检定（如意志）不加值。"""
        g, inv, enemy, inst, impl = _build_game("ice_pick_lv1", IcePick)
        g.chaos_bag.tokens = [ChaosTokenType.ZERO]
        from backend.models.enums import Skill

        impl.use(g.state, "inv1")
        result = g.skill_test_engine.run_test(
            "inv1", Skill.WILLPOWER, difficulty=3)
        # 意志3 + 0 = 3 恰好成功；若误加+1则 extra 可见 ice_pick_bonus
        assert result.extra.get("skill_bonus_sources", []) == [] or all(
            s["reason"] != "ice_pick_bonus"
            for s in result.extra.get("skill_bonus_sources", [])
        )


class TestIcePickLv3:
    def test_fight_discard_for_bonus_damage(self):
        """攻击成功：自动丢弃破冰锥，本次攻击+1伤害。"""
        g, inv, enemy, inst, impl = _build_game("ice_pick_lv3", IcePickLv3)
        g.chaos_bag.tokens = [ChaosTokenType.ZERO]

        impl.use(g.state, "inv1")
        ok = g.action_resolver.perform_action(
            "inv1", Action.FIGHT, enemy_instance_id="e1")
        assert ok is True
        assert enemy.damage == 2  # 基础1 + 破冰锥1
        assert "ice_pick_lv3" in inv.discard
        assert "pick_1" not in inv.play_area

    def test_investigate_discard_for_extra_clue(self):
        """调查成功：自动丢弃破冰锥，额外发现1个线索。"""
        g, inv, enemy, inst, impl = _build_game("ice_pick_lv3", IcePickLv3)
        g.chaos_bag.tokens = [ChaosTokenType.ZERO]
        loc = g.state.get_location("test_location")

        impl.use(g.state, "inv1")
        # 敌人交战中的调查会触发趁乱攻击——先解除交战简化测试
        inv.threat_area.remove("e1")
        loc.enemies.append("e1")
        ok = g.action_resolver.perform_action("inv1", Action.INVESTIGATE)
        assert ok is True
        # 智力3+1=4 对隐蔽值3：基础1 + 额外1 = 2线索
        assert inv.clues == 2
        assert loc.clues == 1
        assert "ice_pick_lv3" in inv.discard

    def test_no_discard_on_failure(self):
        """检定失败：不丢弃（加值仍生效过）。"""
        g, inv, enemy, inst, impl = _build_game("ice_pick_lv3", IcePickLv3)
        g.chaos_bag.tokens = [ChaosTokenType.AUTO_FAIL]

        impl.use(g.state, "inv1")
        g.action_resolver.perform_action(
            "inv1", Action.FIGHT, enemy_instance_id="e1")
        assert enemy.damage == 0
        assert "pick_1" in inv.play_area
