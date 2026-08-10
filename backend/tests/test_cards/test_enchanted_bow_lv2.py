"""Tests for Enchanted Bow (Level 2). (08118)

消耗：攻击，必须用意志或敏捷代替战斗并+1技能值，+1伤害；
可额外花1充能瞄准连接地点非精英敌人（忽略冷漠/反击——反击忽略为引擎缺口，
仅记录标记）。
"""

import pytest
from backend.cards.mystic.enchanted_bow_lv2 import EnchantedBow
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent, Skill
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, ScenarioState,
)
from backend.tests.conftest import make_asset_data, make_investigator_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()
    inv_data = make_investigator_data(willpower=5, agility=4, combat=2)
    state.card_database[inv_data.id] = inv_data
    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1",
    )
    state.investigators["inv1"] = inv
    state.card_database["enchanted_bow_lv2"] = make_asset_data(
        id="enchanted_bow_lv2", name="Enchanted Bow",
        traits=["spell", "blessed", "weapon", "ranged"], uses={"charges": 3},
    )
    inst = CardInstance(
        instance_id="inst_bow", card_id="enchanted_bow_lv2",
        owner_id="inv1", controller_id="inv1",
    )
    inst.uses = {"charges": 3}
    state.cards_in_play["inst_bow"] = inst
    inv.play_area.append("inst_bow")
    impl = EnchantedBow("inst_bow")
    impl.register(bus, "inst_bow")
    return state, bus, inv, inst, impl


def _combat_ctx(state, amount=2):
    return EventContext(
        game_state=state, event=GameEvent.SKILL_VALUE_DETERMINED,
        investigator_id="inv1", skill_type=Skill.COMBAT, amount=amount,
        source="inst_bow",
    )


class TestEnchantedBow:
    def test_activate_exhausts(self, setup):
        state, bus, inv, inst, impl = setup
        assert impl.activate(state, "inv1") is True
        assert inst.exhausted is True

    def test_willpower_substitute_plus_1(self, setup):
        """意志(5)代替战斗(2)，+1技能值。"""
        state, bus, inv, inst, impl = setup
        impl.activate(state, "inv1", skill=Skill.WILLPOWER)
        ctx = _combat_ctx(state)
        bus.emit(ctx)
        assert ctx.amount == 6  # 2 + (5-2) + 1

    def test_agility_substitute_plus_1(self, setup):
        state, bus, inv, inst, impl = setup
        impl.activate(state, "inv1", skill=Skill.AGILITY)
        ctx = _combat_ctx(state)
        bus.emit(ctx)
        assert ctx.amount == 5  # 2 + (4-2) + 1

    def test_bonus_damage(self, setup):
        state, bus, inv, inst, impl = setup
        impl.activate(state, "inv1")
        ctx = EventContext(
            game_state=state, event=GameEvent.SKILL_TEST_SUCCESSFUL,
            investigator_id="inv1", skill_type=Skill.COMBAT, success=True,
            source="inst_bow",
        )
        bus.emit(ctx)
        assert ctx.extra["bonus_damage"] == 1

    def test_ranged_spends_charge(self, setup):
        """远程选项：额外花1充能并记录忽略关键词标记。"""
        state, bus, inv, inst, impl = setup
        assert impl.activate(state, "inv1", ranged=True) is True
        assert inst.uses["charges"] == 2
        ctx = EventContext(
            game_state=state, event=GameEvent.SKILL_TEST_SUCCESSFUL,
            investigator_id="inv1", skill_type=Skill.COMBAT, success=True,
            source="inst_bow",
        )
        bus.emit(ctx)
        assert ctx.extra["enchanted_bow_ignore_aloof_retaliate"] is True

    def test_ranged_requires_charge(self, setup):
        state, bus, inv, inst, impl = setup
        inst.uses["charges"] = 0
        assert impl.activate(state, "inv1", ranged=True) is False
