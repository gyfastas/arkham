"""Tests for Earthly Serenity (Level 1 / Level 4). (08117/08119)

[action]意志检定：成功且每超难度1点，花1充能治愈同地点调查员1伤害/恐惧
（简化：自动治疗自己优先、先伤害后恐惧）；成功且等于难度时失去资源
（lv1 失1、lv4 失2）。
"""

import pytest
from backend.cards.mystic.earthly_serenity_lv1 import EarthlySerenity
from backend.cards.mystic.earthly_serenity_lv4 import EarthlySerenityLv4
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent, Skill
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, ScenarioState,
)
from backend.tests.conftest import make_asset_data, make_investigator_data


def _make(card_id, impl_cls, charges):
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()
    inv_data = make_investigator_data(willpower=5)
    state.card_database[inv_data.id] = inv_data
    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1",
        resources=3,
    )
    state.investigators["inv1"] = inv
    state.card_database[card_id] = make_asset_data(
        id=card_id, name="Earthly Serenity", traits=["spell"],
        uses={"charges": charges},
    )
    inst = CardInstance(
        instance_id="inst_es", card_id=card_id,
        owner_id="inv1", controller_id="inv1",
    )
    inst.uses = {"charges": charges}
    state.cards_in_play["inst_es"] = inst
    inv.play_area.append("inst_es")
    impl = impl_cls("inst_es")
    impl.register(bus, "inst_es")
    return state, bus, inv, inst, impl


def _success(state, bus, modified, difficulty):
    ctx = EventContext(
        game_state=state, event=GameEvent.SKILL_TEST_SUCCESSFUL,
        investigator_id="inv1", skill_type=Skill.WILLPOWER, success=True,
        modified_skill=modified, difficulty=difficulty,
    )
    bus.emit(ctx)
    return ctx


class TestEarthlySerenityLv1:
    def test_heal_per_margin_spends_charges(self):
        """超难度3点：花3充能治愈3点（先伤害后恐惧）。"""
        state, bus, inv, inst, impl = _make(
            "earthly_serenity_lv1", EarthlySerenity, 4)
        inv.damage = 2
        inv.horror = 2
        impl.activate(state, "inv1")
        ctx = _success(state, bus, modified=4, difficulty=1)
        assert inv.damage == 0
        assert inv.horror == 1
        assert inst.uses["charges"] == 1
        assert len(ctx.extra["earthly_serenity_lv1_healed"]) == 3

    def test_heal_capped_by_charges(self):
        """超出点数多于充能时按充能封顶。"""
        state, bus, inv, inst, impl = _make(
            "earthly_serenity_lv1", EarthlySerenity, 1)
        inv.damage = 3
        impl.activate(state, "inv1")
        _success(state, bus, modified=5, difficulty=1)
        assert inv.damage == 2
        assert inst.uses["charges"] == 0

    def test_succeed_by_zero_loses_resource(self):
        """成功且等于难度：失去1资源。"""
        state, bus, inv, inst, impl = _make(
            "earthly_serenity_lv1", EarthlySerenity, 4)
        impl.activate(state, "inv1")
        ctx = _success(state, bus, modified=1, difficulty=1)
        assert inv.resources == 2
        assert ctx.extra["earthly_serenity_lv1_resource_lost"] == 1

    def test_no_heal_without_armed(self):
        state, bus, inv, inst, impl = _make(
            "earthly_serenity_lv1", EarthlySerenity, 4)
        inv.damage = 1
        _success(state, bus, modified=5, difficulty=1)
        assert inv.damage == 1


class TestEarthlySerenityLv4:
    def test_succeed_by_zero_loses_2_resources(self):
        state, bus, inv, inst, impl = _make(
            "earthly_serenity_lv4", EarthlySerenityLv4, 6)
        impl.activate(state, "inv1")
        ctx = _success(state, bus, modified=0, difficulty=0)
        assert inv.resources == 1
        assert ctx.extra["earthly_serenity_lv4_resource_lost"] == 2

    def test_heal_with_six_charges(self):
        state, bus, inv, inst, impl = _make(
            "earthly_serenity_lv4", EarthlySerenityLv4, 6)
        inv.horror = 4
        impl.activate(state, "inv1")
        _success(state, bus, modified=3, difficulty=0)
        assert inv.horror == 1
        assert inst.uses["charges"] == 3
