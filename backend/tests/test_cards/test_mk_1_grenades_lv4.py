"""Tests for Mk 1 Grenades (Level 4). (05273)

[行动]花费1补给：攻击，+2战斗；成功时对被攻击敌人所在地点的每个敌人和
每位其他调查员造成2点伤害（额外伤害加给被攻击敌人）。
"""

import pytest
from backend.cards.guardian.mk_1_grenades_lv4 import Mk1Grenades
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

    inv_data = make_investigator_data(combat=4)
    g.register_card_data(inv_data)
    inv_data2 = make_investigator_data(id="inv2_card", name="Second")
    g.register_card_data(inv_data2)
    g.register_card_data(make_location_data())
    g.register_card_data(CardData(
        id="mk_1_grenades_lv4", name="Mk 1 Grenades", name_cn="Mk 1手雷",
        type=CardType.ASSET, card_class=PlayerClass.GUARDIAN, cost=3,
        traits=["item", "weapon", "ranged"], uses={"suppliess": 3},
    ))
    g.register_card_data(make_enemy_data(
        id="target_enemy", name="Target", fight=3, health=10))
    g.register_card_data(make_enemy_data(
        id="frail_enemy", name="Frail", fight=2, health=2))

    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_investigator("inv2", inv_data2, starting_location="test_location")
    g.add_location("test_location", g.state.get_card_data("test_location"), clues=0)
    g.card_registry.register_class(Mk1Grenades)
    return g


def _setup(game):
    inv = game.state.get_investigator("inv1")
    weapon = game.state.next_instance_id()
    game.state.cards_in_play[weapon] = CardInstance(
        instance_id=weapon, card_id="mk_1_grenades_lv4",
        owner_id="inv1", controller_id="inv1", uses={"suppliess": 3},
    )
    inv.play_area.append(weapon)
    game.card_registry.activate_card(
        "mk_1_grenades_lv4", weapon, game.event_bus)
    game.state.cards_in_play["enemy_1"] = CardInstance(
        instance_id="enemy_1", card_id="target_enemy",
        owner_id="scenario", controller_id="scenario",
    )
    inv.threat_area.append("enemy_1")
    inv.actions_remaining = 3
    return weapon


class TestMk1Grenades:
    def test_area_damage_on_success(self, game):
        """成功：目标2点；同地点另一敌人2点（2生命→被击败）；另一调查员2点。"""
        weapon = _setup(game)
        # 同地点未交战敌人
        game.state.cards_in_play["enemy_2"] = CardInstance(
            instance_id="enemy_2", card_id="frail_enemy",
            owner_id="scenario", controller_id="scenario",
        )
        game.state.get_location("test_location").enemies.append("enemy_2")
        inv2 = game.state.get_investigator("inv2")
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]

        game.action_resolver.perform_action(
            "inv1", Action.FIGHT,
            enemy_instance_id="enemy_1", weapon_instance_id=weapon,
        )
        target = game.state.get_card_instance("enemy_1")
        assert target.damage == 2  # 标准伤害1替换为2
        # 同地点另一敌人受2点并被击败（生命2）
        assert "enemy_2" not in game.state.cards_in_play
        assert "frail_enemy" in game.state.scenario.encounter_discard
        # 同地点其他调查员受2点
        assert inv2.damage == 2
        # 消耗1补给（数据键笔误 suppliess 兼容）
        assert game.state.get_card_instance(weapon).uses["suppliess"] == 2

    def test_no_supply_cancels_attack(self, game):
        """没有补给：无法以本卡攻击。"""
        weapon = _setup(game)
        game.state.get_card_instance(weapon).uses["suppliess"] = 0
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]

        result = game.action_resolver.perform_action(
            "inv1", Action.FIGHT,
            enemy_instance_id="enemy_1", weapon_instance_id=weapon,
        )
        assert result is False
        assert game.state.get_card_instance("enemy_1").damage == 0

    def test_discard_when_supplies_run_out(self, game):
        """最后一次补给用完：攻击结算后弃置本卡。"""
        weapon = _setup(game)
        game.state.get_card_instance(weapon).uses["suppliess"] = 1
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]

        game.action_resolver.perform_action(
            "inv1", Action.FIGHT,
            enemy_instance_id="enemy_1", weapon_instance_id=weapon,
        )
        inv = game.state.get_investigator("inv1")
        assert weapon not in inv.play_area
        assert "mk_1_grenades_lv4" in inv.discard
