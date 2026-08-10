"""Tests for Delilah O'Rourke (Level 3)."""

import pytest
from backend.cards.rogue.delilah_orourke_lv3 import DelilahORourke
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent, Skill
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, LocationState, ScenarioState,
)
from backend.tests.conftest import (
    make_enemy_data, make_investigator_data, make_location_data,
)


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()
    inv_data = make_investigator_data(combat=3, agility=3)
    state.card_database[inv_data.id] = inv_data
    loc_data = make_location_data(id="loc1")
    state.card_database["loc1"] = loc_data
    state.locations["loc1"] = LocationState(
        location_id="loc1", card_data=loc_data, revealed=True,
    )
    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1",
    )
    inv.resources = 5
    state.investigators["inv1"] = inv

    enemy_data = make_enemy_data(evade=3, health=10)
    state.card_database["test_enemy"] = enemy_data
    state.cards_in_play["enemy_1"] = CardInstance(
        instance_id="enemy_1", card_id="test_enemy",
        owner_id="scenario", controller_id="scenario",
    )
    state.locations["loc1"].enemies.append("enemy_1")

    impl = DelilahORourke("delilah_inst")
    impl.register(bus, "delilah_inst")
    ci = CardInstance(
        instance_id="delilah_inst", card_id="delilah_orourke_lv3",
        owner_id="inv1", controller_id="inv1",
    )
    state.cards_in_play["delilah_inst"] = ci
    inv.play_area.append("delilah_inst")
    return state, bus, inv, impl, ci


class TestDelilahORourke:
    def test_passive_combat_and_agility(self, setup):
        """在场期间 +1战斗/+1敏捷。"""
        state, bus, inv, impl, ci = setup
        for skill in (Skill.COMBAT, Skill.AGILITY):
            ctx = EventContext(
                game_state=state, event=GameEvent.SKILL_VALUE_DETERMINED,
                investigator_id="inv1", skill_type=skill, amount=3,
            )
            bus.emit(ctx)
            assert ctx.amount == 4
        # 其他技能无加成
        ctx = EventContext(
            game_state=state, event=GameEvent.SKILL_VALUE_DETERMINED,
            investigator_id="inv1", skill_type=Skill.WILLPOWER, amount=3,
        )
        bus.emit(ctx)
        assert ctx.amount == 3

    def test_activate_spends_evade_cost_deals_1(self, setup):
        """[快速]消耗+花X资源（X=躲避值3）：对敌人造成1伤害。"""
        state, bus, inv, impl, ci = setup
        enemy = state.get_card_instance("enemy_1")
        assert impl.activate(state, "inv1", "enemy_1") is True
        assert inv.resources == 2  # 5-3
        assert ci.exhausted is True
        assert enemy.damage == 1

    def test_exhausted_enemy_takes_2(self, setup):
        """目标已横置：造成2伤害。"""
        state, bus, inv, impl, ci = setup
        enemy = state.get_card_instance("enemy_1")
        enemy.exhausted = True
        assert impl.activate(state, "inv1", "enemy_1") is True
        assert enemy.damage == 2

    def test_insufficient_resources(self, setup):
        state, bus, inv, impl, ci = setup
        inv.resources = 2  # < 躲避值3
        assert impl.activate(state, "inv1", "enemy_1") is False
        assert ci.exhausted is False

    def test_already_exhausted_delilah(self, setup):
        state, bus, inv, impl, ci = setup
        ci.exhausted = True
        assert impl.activate(state, "inv1", "enemy_1") is False

    def test_target_not_at_location_rejected(self, setup):
        state, bus, inv, impl, ci = setup
        state.locations["loc1"].enemies.remove("enemy_1")
        assert impl.activate(state, "inv1", "enemy_1") is False
