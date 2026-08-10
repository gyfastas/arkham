"""Tests for M1918 BAR (Level 4). (04229)

[行动]花费1-5弹药：攻击，+X战斗，伤害替换为X。
"""

import pytest
from backend.cards.guardian.m1918_bar_lv4 import M1918Bar
from backend.engine.game import Game
from backend.models.enums import (
    Action, CardType, ChaosTokenType, PlayerClass, SlotType,
)
from backend.models.state import CardData, CardInstance
from backend.tests.conftest import (
    make_enemy_data, make_investigator_data, make_location_data,
)


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)

    inv_data = make_investigator_data(combat=3)
    g.register_card_data(inv_data)
    g.register_card_data(make_location_data())
    g.register_card_data(CardData(
        id="m1918_bar_lv4", name="M1918 BAR", name_cn="M1918 BAR",
        type=CardType.ASSET, card_class=PlayerClass.GUARDIAN, cost=5,
        slots=[SlotType.HAND, SlotType.HAND],
        traits=["item", "weapon", "firearm"], uses={"ammo": 8},
    ))
    g.register_card_data(make_enemy_data(fight=3, health=10))

    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", g.state.get_card_data("test_location"), clues=0)
    g.card_registry.register_class(M1918Bar)
    return g


def _setup(game):
    inv = game.state.get_investigator("inv1")
    weapon = game.state.next_instance_id()
    game.state.cards_in_play[weapon] = CardInstance(
        instance_id=weapon, card_id="m1918_bar_lv4",
        owner_id="inv1", controller_id="inv1",
        slot_used=[SlotType.HAND, SlotType.HAND], uses={"ammo": 8},
    )
    inv.play_area.append(weapon)
    impl = game.card_registry.activate_card(
        "m1918_bar_lv4", weapon, game.event_bus)
    game.state.cards_in_play["enemy_1"] = CardInstance(
        instance_id="enemy_1", card_id="test_enemy",
        owner_id="scenario", controller_id="scenario",
    )
    inv.threat_area.append("enemy_1")
    inv.actions_remaining = 3
    return weapon, impl


class TestM1918Bar:
    def test_spend_3_ammo_3_damage(self, game):
        """花3弹药：+3战斗，伤害替换为3。"""
        weapon, impl = _setup(game)
        assert impl.activate_fight(game.state, "inv1", x=3) is True
        assert game.state.get_card_instance(weapon).uses["ammo"] == 5
        game.chaos_bag.tokens = [ChaosTokenType.PLUS_1]

        game.action_resolver.perform_action(
            "inv1", Action.FIGHT,
            enemy_instance_id="enemy_1", weapon_instance_id=weapon,
        )
        enemy = game.state.get_card_instance("enemy_1")
        assert enemy.damage == 3  # X=3 替代标准伤害1

    def test_x_out_of_range_rejected(self, game):
        """X 超出1-5或弹药不足：不武装不扣费。"""
        weapon, impl = _setup(game)
        assert impl.activate_fight(game.state, "inv1", x=0) is False
        assert impl.activate_fight(game.state, "inv1", x=6) is False
        assert impl.activate_fight(game.state, "inv1", x=9) is False
        inst = game.state.get_card_instance(weapon)
        assert inst.uses["ammo"] == 8
        # 弹药不足
        inst.uses["ammo"] = 2
        assert impl.activate_fight(game.state, "inv1", x=5) is False
        assert inst.uses["ammo"] == 2

    def test_combat_bonus_scales_with_x(self, game):
        """花5弹药：+5战斗（用极低基础战斗验证加值）。"""
        game.state.get_investigator("inv1").card_data.skills.combat = 1
        weapon, impl = _setup(game)
        assert impl.activate_fight(game.state, "inv1", x=5) is True
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]

        game.action_resolver.perform_action(
            "inv1", Action.FIGHT,
            enemy_instance_id="enemy_1", weapon_instance_id=weapon,
        )
        # 1 + 5 + 0 = 6 >= 3 → 成功，5点伤害
        enemy = game.state.get_card_instance("enemy_1")
        assert enemy.damage == 5
