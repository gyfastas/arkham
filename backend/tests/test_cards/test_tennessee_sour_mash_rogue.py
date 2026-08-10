"""Tests for Tennessee Sour Mash — Rogue versions (Level 0: 05117, Level 3: 05190).

Note: survivor/tennessee_sour_mash_lv3 (05191) shares the lv3 card_id in the
registry; these tests import the rogue classes directly.
"""

import pytest

from backend.cards.rogue.tennessee_sour_mash_lv0 import TennesseeSourMashRogue
from backend.cards.rogue.tennessee_sour_mash_lv3 import TennesseeSourMashRogueLv3
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent, Skill
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, ScenarioState,
)
from backend.tests.conftest import make_investigator_data


def _make_state(bus, card_id, cls):
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    inv_data = make_investigator_data(willpower=3, combat=3)
    state.card_database[inv_data.id] = inv_data
    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1")
    state.investigators["inv1"] = inv
    inst = CardInstance(
        instance_id="tsm_inst", card_id=card_id,
        owner_id="inv1", controller_id="inv1",
        uses={"suppliess": 2},  # 源数据笔误键名
    )
    state.cards_in_play["tsm_inst"] = inst
    inv.play_area.append("tsm_inst")
    impl = cls("tsm_inst")
    impl.register(bus, "tsm_inst")
    return state, inv, inst, impl


def _skill_value(bus, state, skill, amount, source=None):
    ctx = EventContext(
        game_state=state,
        event=GameEvent.SKILL_VALUE_DETERMINED,
        investigator_id="inv1",
        skill_type=skill,
        amount=amount,
        source=source,
    )
    bus.emit(ctx)
    return ctx


class TestTennesseeSourMashLv0:
    @pytest.fixture
    def setup(self):
        bus = EventBus()
        return (bus,) + _make_state(bus, "tennessee_sour_mash_lv0", TennesseeSourMashRogue)

    def test_willpower_boost_spends_supply_and_exhausts(self, setup):
        bus, state, inv, inst, impl = setup
        assert impl.activate_willpower(state, "inv1") is True
        assert inst.uses["suppliess"] == 1
        assert inst.exhausted is True
        ctx = _skill_value(bus, state, Skill.WILLPOWER, 3)
        assert ctx.amount == 5  # +2

    def test_willpower_boost_requires_supply(self, setup):
        bus, state, inv, inst, impl = setup
        inst.uses["suppliess"] = 0
        assert impl.activate_willpower(state, "inv1") is False

    def test_fight_discards_and_boosts_combat(self, setup):
        bus, state, inv, inst, impl = setup
        assert impl.activate_fight(state, "inv1", "enemy_1") is True
        assert "tsm_inst" not in inv.play_area
        assert "tsm_inst" not in state.cards_in_play
        assert "tennessee_sour_mash_lv0" in inv.discard
        ctx = _skill_value(bus, state, Skill.COMBAT, 3, source="tsm_inst")
        assert ctx.amount == 6  # +3

    def test_fight_no_bonus_damage_lv0(self, setup):
        bus, state, inv, inst, impl = setup
        impl.activate_fight(state, "inv1", "enemy_1")
        ctx = EventContext(
            game_state=state,
            event=GameEvent.SKILL_TEST_SUCCESSFUL,
            investigator_id="inv1",
            skill_type=Skill.COMBAT,
            success=True,
            modified_skill=6,
            difficulty=3,
            source="tsm_inst",
        )
        bus.emit(ctx)
        assert "bonus_damage" not in ctx.extra


class TestTennesseeSourMashLv3:
    @pytest.fixture
    def setup(self):
        bus = EventBus()
        return (bus,) + _make_state(bus, "tennessee_sour_mash_lv3", TennesseeSourMashRogueLv3)

    def test_willpower_boost_plus_three(self, setup):
        bus, state, inv, inst, impl = setup
        assert impl.activate_willpower(state, "inv1") is True
        ctx = _skill_value(bus, state, Skill.WILLPOWER, 3)
        assert ctx.amount == 6  # +3

    def test_fight_plus_three_combat_plus_one_damage(self, setup):
        bus, state, inv, inst, impl = setup
        assert impl.activate_fight(state, "inv1", "enemy_1") is True
        ctx = _skill_value(bus, state, Skill.COMBAT, 3, source="tsm_inst")
        assert ctx.amount == 6  # +3
        ctx2 = EventContext(
            game_state=state,
            event=GameEvent.SKILL_TEST_SUCCESSFUL,
            investigator_id="inv1",
            skill_type=Skill.COMBAT,
            success=True,
            modified_skill=6,
            difficulty=3,
            source="tsm_inst",
        )
        bus.emit(ctx2)
        assert ctx2.extra["bonus_damage"] == 1
