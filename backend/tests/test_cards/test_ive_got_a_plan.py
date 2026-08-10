"""Tests for I've Got a Plan (Level 0)."""

import pytest
from backend.cards.seeker.ive_got_a_plan_lv0 import IveGotAPlan
from backend.engine.event_bus import EventBus, EventContext
from backend.engine.game import Game
from backend.models.enums import Action, ChaosTokenType, GameEvent, Skill
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_enemy_data, make_investigator_data, make_location_data,
)


@pytest.fixture
def game():
    g = Game("test_plan")
    g.chaos_bag.seed(42)
    inv_data = make_investigator_data(intellect=5, combat=2)
    g.register_card_data(inv_data)
    enemy_data = make_enemy_data(fight=4, health=10)
    g.register_card_data(enemy_data)
    loc_data = make_location_data()
    g.register_card_data(loc_data)
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc_data, clues=0)

    enemy = CardInstance(
        instance_id="e1", card_id="test_enemy",
        owner_id="scenario", controller_id="scenario",
    )
    g.state.cards_in_play["e1"] = enemy
    inv = g.state.get_investigator("inv1")
    inv.threat_area.append("e1")
    inv.actions_remaining = 3

    impl = IveGotAPlan("plan_1")
    impl.register(g.event_bus, "plan_1")

    return g, inv, enemy


def _play(game):
    game.event_bus.emit(EventContext(
        game_state=game.state, event=GameEvent.CARD_PLAYED,
        investigator_id="inv1",
        extra={"card_id": "ive_got_a_plan_lv0"},
    ))


class TestIveGotAPlan:
    def test_attack_uses_intellect(self, game):
        """战斗检定用智力(5)代替战斗(2)：对战斗力4的敌人命中。"""
        g, inv, enemy = game
        g.chaos_bag.tokens = [ChaosTokenType.ZERO]
        _play(g)
        # 智力5 vs 难度4 -> 命中（若用战斗2则失败）
        ok = g.action_resolver.perform_action("inv1", Action.FIGHT, enemy_instance_id="e1")
        assert ok is True
        assert enemy.damage >= 1

    def test_bonus_damage_per_clue_max_3(self, game):
        """每持有1条线索+1伤害（最多+3）：4条线索也只+3。"""
        g, inv, enemy = game
        inv.clues = 4
        g.chaos_bag.tokens = [ChaosTokenType.ZERO]
        _play(g)
        g.action_resolver.perform_action("inv1", Action.FIGHT, enemy_instance_id="e1")
        assert enemy.damage == 1 + 3  # 基础1 + 上限3

    def test_bonus_damage_scales_with_clues(self, game):
        """2条线索 → +2伤害。"""
        g, inv, enemy = game
        inv.clues = 2
        g.chaos_bag.tokens = [ChaosTokenType.ZERO]
        _play(g)
        g.action_resolver.perform_action("inv1", Action.FIGHT, enemy_instance_id="e1")
        assert enemy.damage == 1 + 2

    def test_effect_cleared_after_test(self, game):
        """武装状态在一次检定后清除：后续攻击回到战斗值且无加成。"""
        g, inv, enemy = game
        inv.clues = 3
        g.chaos_bag.tokens = [ChaosTokenType.ZERO, ChaosTokenType.ZERO]
        _play(g)
        g.action_resolver.perform_action("inv1", Action.FIGHT, enemy_instance_id="e1")
        first = enemy.damage
        assert first == 4  # 智力命中 + 1基础 +3线索

        # 第二次攻击：无武装 → 战斗2+0 vs 难度4 → 失败无伤害
        inv.actions_remaining = 3
        g.action_resolver.perform_action("inv1", Action.FIGHT, enemy_instance_id="e1")
        assert enemy.damage == first

    def test_not_armed_no_substitution(self, game):
        """未打出本卡：战斗检定用战斗值。"""
        g, inv, enemy = game
        g.chaos_bag.tokens = [ChaosTokenType.ZERO]
        # 战斗2+0 vs 难度4 -> 失败
        g.action_resolver.perform_action("inv1", Action.FIGHT, enemy_instance_id="e1")
        assert enemy.damage == 0
