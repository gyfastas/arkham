"""Tests for "Eat lead!" (Level 2). (03304)

快速。启动枪械攻击能力时打出：花费额外X子弹，抽标记时额外抽X个，
选择一个结算并忽略其余。
"""

import random

import pytest
from backend.cards.guardian.eat_lead_lv2 import EatLead, _token_rank
from backend.cards.guardian.thirty_two_colt_lv0 import ThirtyTwoColt
from backend.engine.game import Game
from backend.models.enums import (
    CHAOS_TOKEN_VALUES, Action, ChaosTokenType, CardType, PlayerClass, SlotType,
)
from backend.models.state import CardData, CardInstance
from backend.tests.conftest import (
    make_enemy_data, make_event_data, make_investigator_data,
    make_location_data,
)


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)

    inv_data = make_investigator_data(combat=3)
    g.register_card_data(inv_data)
    g.register_card_data(make_location_data())
    g.register_card_data(CardData(
        id="32_colt_lv0", name=".32 Colt", name_cn=".32柯尔特",
        type=CardType.ASSET, card_class=PlayerClass.GUARDIAN, cost=3,
        slots=[SlotType.HAND], traits=["item", "weapon", "firearm"],
        uses={"ammo": 6},
    ))
    g.register_card_data(make_event_data(
        id="eat_lead_lv2", name='"Eat lead!"', cost=0, fast=True,
    ))
    g.register_card_data(make_enemy_data(fight=3, health=5))

    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", g.state.get_card_data("test_location"), clues=2)
    g.card_registry.register_class(ThirtyTwoColt)
    g.card_registry.register_class(EatLead)

    # 装备柯尔特（3子弹）
    inv = g.state.get_investigator("inv1")
    colt = CardInstance(
        instance_id="colt_1", card_id="32_colt_lv0",
        owner_id="inv1", controller_id="inv1",
        slot_used=[SlotType.HAND], uses={"ammo": 3},
    )
    g.state.cards_in_play["colt_1"] = colt
    inv.play_area.append("colt_1")
    g.card_registry.activate_card("32_colt_lv0", "colt_1", g.event_bus)

    enemy = CardInstance(
        instance_id="enemy_1", card_id="test_enemy",
        owner_id="scenario", controller_id="scenario",
    )
    g.state.cards_in_play["enemy_1"] = enemy
    inv.threat_area.append("enemy_1")
    return g


def _arm_eat_lead(game):
    """把吃子弹吧放入手牌并激活实现（绑定混沌袋）。"""
    inv = game.state.get_investigator("inv1")
    inv.hand.append("eat_lead_lv2")
    game.card_registry.activate_card(
        "eat_lead_lv2", "eatlead_1", game.event_bus, chaos_bag=game.chaos_bag,
    )


class TestEatLead:
    def test_extra_tokens_choose_best(self, game):
        """自动打出：花光额外2子弹，3个标记中自动选择结算值最高的。"""
        _arm_eat_lead(game)
        tokens = [ChaosTokenType.MINUS_2, ChaosTokenType.ZERO, ChaosTokenType.PLUS_1]
        game.chaos_bag.tokens = list(tokens)
        game.chaos_bag.seed(1)  # 抽取序列 [0,2,0]：原标记-2，额外为+1与0

        # 复现袋子的抽取消耗顺序（ST.3 抽1个 + 吃子弹吧额外抽2个）
        rng = random.Random(1)
        drawn = [tokens[rng.randint(0, 2)] for _ in range(3)]
        best = max(drawn, key=_token_rank)
        expected_modifier = CHAOS_TOKEN_VALUES[best]
        assert drawn[0] == ChaosTokenType.MINUS_2  # 原标记
        assert best == ChaosTokenType.PLUS_1  # 换入更优标记，走交换分支

        inv = game.state.get_investigator("inv1")
        inv.actions_remaining = 3

        # CHAOS_TOKEN_RESOLVED 的 extra 不进检定结果，用探针捕获标记
        from backend.models.enums import GameEvent, TimingPriority
        seen = {}
        game.event_bus.register(
            GameEvent.CHAOS_TOKEN_RESOLVED,
            lambda ctx: seen.update(ctx.extra),
            priority=TimingPriority.AFTER,
        )

        game.action_resolver.perform_action(
            "inv1", Action.FIGHT,
            enemy_instance_id="enemy_1", weapon_instance_id="colt_1",
        )

        colt = game.state.get_card_instance("colt_1")
        assert colt.uses["ammo"] == 0  # 1（攻击费用）+ 2（额外）全部花掉
        assert "eat_lead_lv2" in inv.discard  # 自动打出
        assert "eat_lead_lv2" not in inv.hand

        result = game.skill_test_engine._last_result
        assert result.token_modifier == expected_modifier  # 结算的是最优标记
        assert seen.get("eat_lead_chose") == best.value
        assert seen.get("eat_lead_extra_tokens") == ["+1", "-2"]
        # 3 + 1（+1标记）= 4 vs 战斗3：命中，柯尔特+1伤害
        assert result.success is True
        assert game.state.get_card_instance("enemy_1").damage == 2

    def test_not_triggered_by_non_firearm(self, game):
        """徒手攻击（非枪械能力）不触发。"""
        _arm_eat_lead(game)
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]

        inv = game.state.get_investigator("inv1")
        inv.actions_remaining = 3
        game.action_resolver.perform_action(
            "inv1", Action.FIGHT, enemy_instance_id="enemy_1",
        )
        assert "eat_lead_lv2" in inv.hand  # 未打出

    def test_not_triggered_without_extra_ammo(self, game):
        """枪械没有额外子弹时不自动打出。"""
        _arm_eat_lead(game)
        game.state.get_card_instance("colt_1").uses["ammo"] = 1  # 仅够攻击本身
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]

        inv = game.state.get_investigator("inv1")
        inv.actions_remaining = 3
        game.action_resolver.perform_action(
            "inv1", Action.FIGHT,
            enemy_instance_id="enemy_1", weapon_instance_id="colt_1",
        )
        assert "eat_lead_lv2" in inv.hand  # 未打出
        assert game.state.get_card_instance("colt_1").uses["ammo"] == 0
