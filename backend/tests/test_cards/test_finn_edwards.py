"""Tests for Finn Edwards investigator ability."""

import pytest
from backend.cards.rogue.finn_edwards import FinnEdwards
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import ChaosTokenType, GameEvent, Skill
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_asset_data, make_enemy_data, make_investigator_data,
    make_location_data,
)


def _make_game():
    g = Game("test_finn")
    g.chaos_bag.seed(42)

    inv_data = make_investigator_data(id="finn_edwards", name="Finn Edwards",
                                      intellect=4, agility=4)
    g.register_card_data(inv_data)
    loc_data = make_location_data(clue_value=2)
    g.register_card_data(loc_data)
    enemy_data = make_enemy_data(fight=3, health=3, evade=3)
    g.register_card_data(enemy_data)
    g.register_card_data(make_asset_data(id="asset_a"))

    g.add_investigator("finn", inv_data, deck=["filler"] * 10,
                       starting_location="test_location")
    g.add_location("test_location", loc_data, clues=2)
    return g


def _impl(g):
    return g.card_registry.active_instances["investigator_finn"]


def _add_enemy(g, instance_id, engaged=False, exhausted=False):
    enemy = CardInstance(
        instance_id=instance_id, card_id="test_enemy",
        owner_id="scenario", controller_id="scenario",
        exhausted=exhausted,
    )
    g.state.cards_in_play[instance_id] = enemy
    inv = g.state.get_investigator("finn")
    if engaged:
        inv.threat_area.append(instance_id)
    else:
        g.state.locations["test_location"].enemies.append(instance_id)
    return enemy


def _turn_begins(g):
    g.event_bus.emit(EventContext(
        game_state=g.state,
        event=GameEvent.INVESTIGATOR_TURN_BEGINS,
        investigator_id="finn",
    ))


class TestSetupActivation:
    def test_setup_activates_impl(self):
        g = _make_game()
        g.setup()
        assert isinstance(_impl(g), FinnEdwards)


class TestExtraEvadeAction:
    def test_evade_action_success(self):
        """额外行动躲避交战敌人：成功消耗并解除交战，不占普通行动。"""
        g = _make_game()
        g.setup()
        impl = _impl(g)
        inv = g.state.get_investigator("finn")
        inv.actions_remaining = 3
        _add_enemy(g, "enemy_1", engaged=True)

        _turn_begins(g)
        g.chaos_bag.tokens = [ChaosTokenType.PLUS_1]  # 4+1 vs 3 成功
        assert impl.activate_evade(g, "finn", "enemy_1") is True

        enemy = g.state.get_card_instance("enemy_1")
        assert enemy.exhausted is True
        assert "enemy_1" not in inv.threat_area
        assert "enemy_1" in g.state.locations["test_location"].enemies
        assert inv.actions_remaining == 3  # 额外行动不扣普通行动

    def test_evade_action_once_per_turn(self):
        """额外行动每回合1次：回合结束失效，下回合重新获得。"""
        g = _make_game()
        g.setup()
        impl = _impl(g)
        _add_enemy(g, "enemy_1", engaged=True)
        _add_enemy(g, "enemy_2", engaged=True)

        _turn_begins(g)
        g.chaos_bag.tokens = [ChaosTokenType.PLUS_1]
        assert impl.activate_evade(g, "finn", "enemy_1") is True
        # 本回合第二次不可用
        assert impl.activate_evade(g, "finn", "enemy_2") is False

        g.event_bus.emit(EventContext(
            game_state=g.state,
            event=GameEvent.INVESTIGATOR_TURN_ENDS,
            investigator_id="finn",
        ))
        _turn_begins(g)
        assert impl.activate_evade(g, "finn", "enemy_2") is True

    def test_no_evade_action_outside_turn(self):
        """未到自己回合时不可用。"""
        g = _make_game()
        g.setup()
        impl = _impl(g)
        _add_enemy(g, "enemy_1", engaged=True)
        assert impl.activate_evade(g, "finn", "enemy_1") is False


class TestElderSign:
    def test_bonus_per_exhausted_enemy(self):
        """远古印记：场上每个已消耗敌人+1（非敌人/未消耗不计）。"""
        g = _make_game()
        g.setup()
        _add_enemy(g, "enemy_1", exhausted=True)
        _add_enemy(g, "enemy_2", exhausted=True)
        _add_enemy(g, "enemy_3", exhausted=False)
        # 已消耗的非敌人不计入
        asset = CardInstance(
            instance_id="asset_1", card_id="asset_a",
            owner_id="finn", controller_id="finn", exhausted=True,
        )
        g.state.cards_in_play["asset_1"] = asset

        g.chaos_bag.tokens = [ChaosTokenType.ELDER_SIGN]
        result = g.skill_test_engine.run_test(
            investigator_id="finn", skill_type=Skill.AGILITY, difficulty=99,
        )
        assert result.token_modifier == 2

    def test_discover_clue_on_success_by_2(self):
        """成功且超过难度至少2点：发现所在地点1个线索。"""
        g = _make_game()
        g.setup()
        inv = g.state.get_investigator("finn")
        loc = g.state.locations["test_location"]

        g.chaos_bag.tokens = [ChaosTokenType.ELDER_SIGN]
        # 智力4 +0（无消耗敌人）vs 难度2：成功超2点
        result = g.skill_test_engine.run_test(
            investigator_id="finn", skill_type=Skill.INTELLECT, difficulty=2,
        )
        assert result.success is True
        assert inv.clues == 1
        assert loc.clues == 1

    def test_no_clue_when_margin_below_2(self):
        """成功但不足2点：不发现线索。"""
        g = _make_game()
        g.setup()
        inv = g.state.get_investigator("finn")
        loc = g.state.locations["test_location"]

        g.chaos_bag.tokens = [ChaosTokenType.ELDER_SIGN]
        # 智力4 vs 难度3：成功但只超1点
        result = g.skill_test_engine.run_test(
            investigator_id="finn", skill_type=Skill.INTELLECT, difficulty=3,
        )
        assert result.success is True
        assert inv.clues == 0
        assert loc.clues == 2

    def test_no_clue_on_failure(self):
        """检定失败：不发现线索。"""
        g = _make_game()
        g.setup()
        inv = g.state.get_investigator("finn")

        g.chaos_bag.tokens = [ChaosTokenType.ELDER_SIGN]
        result = g.skill_test_engine.run_test(
            investigator_id="finn", skill_type=Skill.INTELLECT, difficulty=99,
        )
        assert result.success is False
        assert inv.clues == 0
