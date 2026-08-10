"""Tests for Wither (lv0 / lv4)."""

import pytest

from backend.cards.mystic.wither_lv0 import Wither
from backend.cards.mystic.wither_lv4 import WitherLv4
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import ChaosTokenType, GameEvent, Skill
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, ScenarioState,
)
from backend.tests.conftest import (
    make_asset_data, make_enemy_data, make_investigator_data,
)


def _setup(impl_cls, card_id, willpower=5, combat=2, enemy_health=3, enemy_damage=0):
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()

    inv_data = make_investigator_data(willpower=willpower, combat=combat)
    state.card_database[inv_data.id] = inv_data
    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1")
    state.investigators["inv1"] = inv

    enemy_data = make_enemy_data(fight=3, health=enemy_health, evade=3)
    state.card_database["test_enemy"] = enemy_data
    enemy = CardInstance(
        instance_id="enemy1", card_id="test_enemy",
        owner_id="scenario", controller_id="scenario",
    )
    enemy.damage = enemy_damage
    state.cards_in_play["enemy1"] = enemy
    inv.threat_area.append("enemy1")

    state.card_database[card_id] = make_asset_data(id=card_id)
    inst = CardInstance(
        instance_id="inst1", card_id=card_id,
        owner_id="inv1", controller_id="inv1",
    )
    state.cards_in_play["inst1"] = inst
    inv.play_area.append("inst1")

    impl = impl_cls("inst1")
    impl.register(bus, "inst1")
    return state, bus, inv, inst, impl, enemy


def _emit(bus, state, event, **kwargs):
    ctx = EventContext(game_state=state, event=event, investigator_id="inv1", **kwargs)
    bus.emit(ctx)
    return ctx


def _wither_attack_with_symbol(bus, state, impl, token=ChaosTokenType.SKULL):
    impl.activate(state, "inv1", "enemy1")
    _emit(bus, state, GameEvent.FIGHT_ACTION_INITIATED,
          enemy_id="enemy1", source="inst1")
    _emit(bus, state, GameEvent.CHAOS_TOKEN_RESOLVED,
          chaos_token=token, source="inst1", skill_type=Skill.COMBAT)


class TestWitherLv0:
    CID = "wither_lv0"

    def test_willpower_substitute(self):
        state, bus, inv, inst, impl, _ = _setup(Wither, self.CID)
        impl.activate(state, "inv1", "enemy1")
        ctx = _emit(bus, state, GameEvent.SKILL_VALUE_DETERMINED,
                    skill_type=Skill.COMBAT, amount=2, source="inst1")
        assert ctx.amount == 5

    def test_symbol_debuffs_enemy_fight_for_turn(self):
        """符号标记后，本回合对该敌人的战斗检定难度-1（下限1）。"""
        state, bus, inv, inst, impl, enemy = _setup(Wither, self.CID)
        _wither_attack_with_symbol(bus, state, impl)
        _emit(bus, state, GameEvent.SKILL_TEST_ENDS, success=False)
        assert "enemy1" in impl._debuffed
        # 下一次对该敌人的战斗：难度3 → 2
        _emit(bus, state, GameEvent.FIGHT_ACTION_INITIATED, enemy_id="enemy1")
        ctx = _emit(bus, state, GameEvent.SKILL_TEST_BEGINS,
                    skill_type=Skill.COMBAT, difficulty=3)
        assert ctx.difficulty == 2
        _emit(bus, state, GameEvent.SKILL_TEST_ENDS, success=False)
        # 回合结束：过期
        _emit(bus, state, GameEvent.INVESTIGATOR_TURN_ENDS)
        _emit(bus, state, GameEvent.FIGHT_ACTION_INITIATED, enemy_id="enemy1")
        ctx = _emit(bus, state, GameEvent.SKILL_TEST_BEGINS,
                    skill_type=Skill.COMBAT, difficulty=3)
        assert ctx.difficulty == 3

    def test_no_symbol_no_debuff(self):
        state, bus, inv, inst, impl, enemy = _setup(Wither, self.CID)
        _wither_attack_with_symbol(bus, state, impl, token=ChaosTokenType.MINUS_1)
        assert "enemy1" not in impl._debuffed


class TestWitherLv4:
    CID = "wither_lv4"

    def test_willpower_plus_two(self):
        state, bus, inv, inst, impl, _ = _setup(WitherLv4, self.CID)
        impl.activate(state, "inv1", "enemy1")
        ctx = _emit(bus, state, GameEvent.SKILL_VALUE_DETERMINED,
                    skill_type=Skill.COMBAT, amount=2, source="inst1")
        assert ctx.amount == 7

    def test_health_reduction_defeats_damaged_enemy(self):
        """-1生命：已受伤（2/3）的敌人按阈值 max(1, 3-1)=2 立即被击败。"""
        state, bus, inv, inst, impl, enemy = _setup(
            WitherLv4, self.CID, enemy_health=3, enemy_damage=2)
        _wither_attack_with_symbol(bus, state, impl)
        assert "enemy1" not in state.cards_in_play
        assert "enemy1" not in inv.threat_area
        assert "test_enemy" in state.scenario.encounter_discard

    def test_health_reduction_applies_to_later_damage(self):
        """未立即击败时，后续伤害按降低后的阈值复查。"""
        state, bus, inv, inst, impl, enemy = _setup(
            WitherLv4, self.CID, enemy_health=3, enemy_damage=0)
        _wither_attack_with_symbol(bus, state, impl)
        assert "enemy1" in state.cards_in_play  # 0伤，未击败
        _emit(bus, state, GameEvent.SKILL_TEST_ENDS, success=True)
        # 后续造成2伤（阈值2）→ 击败
        enemy.damage += 2
        _emit(bus, state, GameEvent.DAMAGE_DEALT, target="enemy1", amount=2)
        assert "enemy1" not in state.cards_in_play
