"""Tests for Enchanted Blade (Level 0 / Level 3). (05118/05193)

[action]攻击：lv0 +1战斗；lv3 +2战斗。可选花费充能附魔（lv0 至多1、lv3 至多2）：
每充能再+1战斗并+1伤害。
"""

import pytest
from backend.cards.mystic.enchanted_blade_lv0 import EnchantedBlade
from backend.cards.mystic.enchanted_blade_lv3 import EnchantedBladeLv3
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
    inv_data = make_investigator_data(combat=3)
    state.card_database[inv_data.id] = inv_data
    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1",
    )
    state.investigators["inv1"] = inv
    state.card_database["enchanted_blade_lv0"] = make_asset_data(
        id="enchanted_blade_lv0", name="Enchanted Blade",
        traits=["item", "relic", "weapon", "melee"], uses={"charges": 3},
    )
    state.card_database["enchanted_blade_lv3"] = make_asset_data(
        id="enchanted_blade_lv3", name="Enchanted Blade",
        traits=["item", "relic", "weapon", "melee"], uses={"charges": 4},
    )
    return state, bus, inv


def _add_blade(state, bus, inv, card_id, instance_id, impl_cls, charges):
    inst = CardInstance(
        instance_id=instance_id, card_id=card_id,
        owner_id="inv1", controller_id="inv1",
    )
    inst.uses = {"charges": charges}
    state.cards_in_play[instance_id] = inst
    inv.play_area.append(instance_id)
    impl = impl_cls(instance_id)
    impl.register(bus, instance_id)
    return inst, impl


def _combat_ctx(state, instance_id, amount=3):
    return EventContext(
        game_state=state, event=GameEvent.SKILL_VALUE_DETERMINED,
        investigator_id="inv1", skill_type=Skill.COMBAT, amount=amount,
        source=instance_id,
    )


def _success_ctx(state, instance_id):
    return EventContext(
        game_state=state, event=GameEvent.SKILL_TEST_SUCCESSFUL,
        investigator_id="inv1", skill_type=Skill.COMBAT, success=True,
        source=instance_id,
    )


class TestEnchantedBladeLv0:
    def test_base_combat_bonus(self, setup):
        """未附魔：+1战斗，无额外伤害。"""
        state, bus, inv = setup
        _add_blade(state, bus, inv, "enchanted_blade_lv0", "inst_eb", EnchantedBlade, 3)
        ctx = _combat_ctx(state, "inst_eb")
        bus.emit(ctx)
        assert ctx.amount == 4
        sctx = _success_ctx(state, "inst_eb")
        bus.emit(sctx)
        assert "bonus_damage" not in sctx.extra

    def test_empower_adds_combat_and_damage(self, setup):
        """花1充能附魔：再+1战斗并+1伤害。"""
        state, bus, inv = setup
        inst, impl = _add_blade(
            state, bus, inv, "enchanted_blade_lv0", "inst_eb", EnchantedBlade, 3)
        assert impl.empower(state, "inv1", 1) is True
        assert inst.uses["charges"] == 2
        ctx = _combat_ctx(state, "inst_eb")
        bus.emit(ctx)
        assert ctx.amount == 5  # 3 + 1 + 1
        sctx = _success_ctx(state, "inst_eb")
        bus.emit(sctx)
        assert sctx.extra["bonus_damage"] == 1

    def test_empower_rejects_over_limit(self, setup):
        """lv0 至多附魔1充能。"""
        state, bus, inv = setup
        _, impl = _add_blade(
            state, bus, inv, "enchanted_blade_lv0", "inst_eb", EnchantedBlade, 3)
        assert impl.empower(state, "inv1", 2) is False

    def test_empower_cleared_after_test(self, setup):
        state, bus, inv = setup
        _, impl = _add_blade(
            state, bus, inv, "enchanted_blade_lv0", "inst_eb", EnchantedBlade, 3)
        impl.empower(state, "inv1", 1)
        bus.emit(EventContext(
            game_state=state, event=GameEvent.SKILL_TEST_ENDS,
            investigator_id="inv1",
        ))
        ctx = _combat_ctx(state, "inst_eb")
        bus.emit(ctx)
        assert ctx.amount == 4  # 仅基础+1


class TestEnchantedBladeLv3:
    def test_base_plus_2_combat(self, setup):
        state, bus, inv = setup
        _add_blade(state, bus, inv, "enchanted_blade_lv3", "inst_eb3", EnchantedBladeLv3, 4)
        ctx = _combat_ctx(state, "inst_eb3")
        bus.emit(ctx)
        assert ctx.amount == 5  # 3 + 2

    def test_empower_two_charges(self, setup):
        """lv3 可花2充能：+2战斗+2伤害（合计+4战斗/+2伤害）。"""
        state, bus, inv = setup
        inst, impl = _add_blade(
            state, bus, inv, "enchanted_blade_lv3", "inst_eb3", EnchantedBladeLv3, 4)
        assert impl.empower(state, "inv1", 2) is True
        assert inst.uses["charges"] == 2
        ctx = _combat_ctx(state, "inst_eb3")
        bus.emit(ctx)
        assert ctx.amount == 7  # 3 + 2 + 2
        sctx = _success_ctx(state, "inst_eb3")
        bus.emit(sctx)
        assert sctx.extra["bonus_damage"] == 2
