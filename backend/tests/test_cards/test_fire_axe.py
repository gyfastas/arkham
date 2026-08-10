"""Tests for Fire Axe (Level 0)."""

import pytest
from backend.cards.survivor.fire_axe_lv0 import FireAxe
from backend.models.enums import Action, ChaosTokenType, PlayerClass, Skill, SlotType
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_enemy_data, make_investigator_data, make_asset_data, make_location_data,
)
from backend.engine.game import Game


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)
    inv_data = make_investigator_data(combat=3)
    g.register_card_data(inv_data)
    loc = make_location_data()
    g.register_card_data(loc)

    axe_data = make_asset_data(
        id="fire_axe_lv0", name="Fire Axe", cost=1,
        card_class=PlayerClass.SURVIVOR,
        slots=[SlotType.HAND], traits=["item", "weapon", "melee"],
    )
    g.register_card_data(axe_data)
    g.register_card_data(make_enemy_data(fight=3, health=10, evade=3))
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)
    g.card_registry.register_class(FireAxe)
    return g


def _equip_axe(game):
    inv = game.state.get_investigator("inv1")
    iid = game.state.next_instance_id()
    game.state.cards_in_play[iid] = CardInstance(
        instance_id=iid, card_id="fire_axe_lv0",
        owner_id="inv1", controller_id="inv1", slot_used=[SlotType.HAND],
    )
    inv.play_area.append(iid)
    game.card_registry.activate_card("fire_axe_lv0", iid, game.event_bus)
    return iid


def _spawn_enemy(game):
    game.state.cards_in_play["enemy_1"] = CardInstance(
        instance_id="enemy_1", card_id="test_enemy",
        owner_id="scenario", controller_id="scenario",
    )
    game.state.get_investigator("inv1").threat_area.append("enemy_1")
    return game.state.cards_in_play["enemy_1"]


def _fight(game, axe_id=None, token=ChaosTokenType.ZERO):
    inv = game.state.get_investigator("inv1")
    inv.actions_remaining = 3
    game.chaos_bag.tokens = [token]
    game.action_resolver.perform_action(
        "inv1", Action.FIGHT,
        enemy_instance_id="enemy_1",
        weapon_instance_id=axe_id,
    )
    return game.skill_test_engine._last_result


class TestFireAxe:
    def test_card_registered(self, game):
        assert "fire_axe_lv0" in game.card_registry.registered_cards

    def test_no_base_combat_bonus(self, game):
        """消防斧无基础战斗加值（修复幽灵+1）。"""
        axe_id = _equip_axe(game)
        enemy = _spawn_enemy(game)
        inv = game.state.get_investigator("inv1")
        inv.resources = 3

        result = _fight(game, axe_id)

        assert result.modified_skill == 3  # 3 + 0，无加值
        assert result.success is True
        assert enemy.damage == 1           # 资源池非0，无+1伤害

    def test_zero_resources_bonus_damage(self, game):
        """资源池为0：本次攻击+1伤害。"""
        axe_id = _equip_axe(game)
        enemy = _spawn_enemy(game)
        inv = game.state.get_investigator("inv1")
        inv.resources = 0

        result = _fight(game, axe_id)

        assert result.success is True
        assert enemy.damage == 2

    def test_spend_up_to_three_times_for_plus_2_each(self, game):
        """花1资源+2战斗，每次攻击限3次。"""
        axe_id = _equip_axe(game)
        enemy = _spawn_enemy(game)
        inv = game.state.get_investigator("inv1")
        inv.resources = 5

        impl = game.card_registry.active_instances[axe_id]

        for _ in range(3):
            assert impl.spend(game.state, "inv1", Skill.COMBAT) is True
        # 第4次超出每次攻击上限
        assert impl.spend(game.state, "inv1", Skill.COMBAT) is False
        assert inv.resources == 2

        result = _fight(game, axe_id)
        assert result.modified_skill == 3 + 6  # 3×(+2)
        assert result.success is True
        assert enemy.damage == 1               # 资源池非0

    def test_spend_not_applied_to_other_weapons(self, game):
        """武装的加值只对使用消防斧的攻击生效。"""
        axe_id = _equip_axe(game)
        _spawn_enemy(game)
        inv = game.state.get_investigator("inv1")
        inv.resources = 3

        impl = game.card_registry.active_instances[axe_id]
        assert impl.spend(game.state, "inv1", Skill.COMBAT) is True

        # 徒手攻击（不使用消防斧）
        result = _fight(game, None)
        assert result.modified_skill == 3

        # 加值已随检定结束清除，不会泄漏到后续攻击
        result = _fight(game, axe_id)
        assert result.modified_skill == 3
