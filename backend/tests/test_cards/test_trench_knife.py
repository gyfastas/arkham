"""Tests for Trench Knife (Level 0). (03147)

交战行动不引起趁乱攻击；攻击时 +X 战斗（X=与你交战的敌人数量）。
"""

import pytest
from backend.cards.guardian.trench_knife_lv0 import TrenchKnife
from backend.engine.game import Game
from backend.models.enums import (
    Action, ChaosTokenType, CardType, PlayerClass, SlotType,
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
        id="trench_knife_lv0", name="Trench Knife", name_cn="战壕刀",
        type=CardType.ASSET, card_class=PlayerClass.GUARDIAN, cost=1,
        slots=[SlotType.HAND], traits=["item", "weapon", "melee"],
        skill_icons={"combat": 1},
    ))
    g.register_card_data(make_enemy_data(fight=4, health=5, damage=1, horror=1))

    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", g.state.get_card_data("test_location"), clues=2)
    g.card_registry.register_class(TrenchKnife)

    inv = g.state.get_investigator("inv1")
    inst = CardInstance(
        instance_id="knife_1", card_id="trench_knife_lv0",
        owner_id="inv1", controller_id="inv1", slot_used=[SlotType.HAND],
    )
    g.state.cards_in_play["knife_1"] = inst
    inv.play_area.append("knife_1")
    g.card_registry.activate_card("trench_knife_lv0", "knife_1", g.event_bus)
    return g


def _spawn_engaged(game, instance_id):
    enemy = CardInstance(
        instance_id=instance_id, card_id="test_enemy",
        owner_id="scenario", controller_id="scenario",
    )
    game.state.cards_in_play[instance_id] = enemy
    game.state.get_investigator("inv1").threat_area.append(instance_id)
    return enemy


def _spawn_at_location(game, instance_id):
    enemy = CardInstance(
        instance_id=instance_id, card_id="test_enemy",
        owner_id="scenario", controller_id="scenario",
    )
    game.state.cards_in_play[instance_id] = enemy
    game.state.get_location("test_location").enemies.append(instance_id)
    return enemy


class TestTrenchKnife:
    def test_combat_bonus_scales_with_engaged_enemies(self, game):
        """与2个敌人交战时攻击 +2 战斗。"""
        _spawn_engaged(game, "enemy_1")
        _spawn_engaged(game, "enemy_2")
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]

        game.action_resolver.perform_action(
            "inv1", Action.FIGHT,
            enemy_instance_id="enemy_1", weapon_instance_id="knife_1",
        )
        result = game.skill_test_engine._last_result
        assert result.modified_skill == 5  # 3 + 2刀 + 0标记
        assert result.success is True  # 5 vs 4

    def test_single_enemy_bonus(self, game):
        """只与1个敌人交战时 +1 战斗（4 vs 4 恰好命中）。"""
        enemy = _spawn_engaged(game, "enemy_1")
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]

        game.action_resolver.perform_action(
            "inv1", Action.FIGHT,
            enemy_instance_id="enemy_1", weapon_instance_id="knife_1",
        )
        result = game.skill_test_engine._last_result
        assert result.modified_skill == 4
        assert enemy.damage == 1

    def test_engage_does_not_provoke_aoo(self, game):
        """交战行动不引起趁乱攻击。"""
        _spawn_engaged(game, "enemy_1")  # 已交战且未横置，正常会AoO
        _spawn_at_location(game, "enemy_2")

        inv = game.state.get_investigator("inv1")
        inv.actions_remaining = 3
        ok = game.action_resolver.perform_action(
            "inv1", Action.ENGAGE, enemy_instance_id="enemy_2",
        )
        assert ok is True
        assert "enemy_2" in inv.threat_area
        assert inv.damage == 0 and inv.horror == 0  # AoO 被取消

    def test_investigate_still_provokes_aoo(self, game):
        """对照：调查行动（有发起事件）仍正常引起趁乱攻击。"""
        _spawn_engaged(game, "enemy_1")
        game.chaos_bag.tokens = [ChaosTokenType.PLUS_1]

        inv = game.state.get_investigator("inv1")
        inv.actions_remaining = 3
        game.action_resolver.perform_action("inv1", Action.INVESTIGATE)
        assert inv.damage == 1 and inv.horror == 1
