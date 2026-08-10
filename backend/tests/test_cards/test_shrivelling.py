"""Tests for Shrivelling (Level 0). (01060)

【行动】花1充能：攻击。用意志代替战斗（无技能加值、无需横置），+1伤害；
揭示 skull/cultist/tablet/elder_thing/auto_fail 时受1恐惧。
"""

import pytest
from backend.cards.mystic.shrivelling_lv0 import Shrivelling
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import ChaosTokenType, GameEvent, Skill
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, ScenarioState,
)
from backend.tests.conftest import make_asset_data, make_investigator_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()

    inv_data = make_investigator_data(willpower=5, combat=2)
    state.card_database[inv_data.id] = inv_data
    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1",
    )
    state.investigators["inv1"] = inv

    state.card_database["shrivelling_lv0"] = make_asset_data(
        id="shrivelling_lv0", name="Shrivelling", traits=["spell"],
        uses={"charges": 4},
    )
    inst = CardInstance(
        instance_id="inst_shriv", card_id="shrivelling_lv0",
        owner_id="inv1", controller_id="inv1",
    )
    inst.uses = {"charges": 4}
    state.cards_in_play["inst_shriv"] = inst
    inv.play_area.append("inst_shriv")

    impl = Shrivelling("inst_shriv")
    impl.register(bus, "inst_shriv")
    return state, bus, inv, inst, impl


class TestShrivelling:
    def test_activate_spends_charge_without_exhaust(self, setup):
        """官方卡面无横置要求。"""
        state, bus, inv, inst, impl = setup
        assert impl.activate(state, "inv1") is True
        assert inst.uses["charges"] == 3
        assert inst.exhausted is False

    def test_willpower_substitute_no_skill_bonus(self, setup):
        """意志(5)代替战斗(2)，无+1（旧实现的+1为编造）。"""
        state, bus, inv, inst, impl = setup
        impl.activate(state, "inv1")
        ctx = EventContext(
            game_state=state, event=GameEvent.SKILL_VALUE_DETERMINED,
            investigator_id="inv1", skill_type=Skill.COMBAT, amount=2,
            source="inst_shriv",
        )
        bus.emit(ctx)
        assert ctx.amount == 5

    def test_no_substitute_without_source(self, setup):
        """武装后徒手攻击（无 weapon source）不适用皱缩术。"""
        state, bus, inv, inst, impl = setup
        impl.activate(state, "inv1")
        ctx = EventContext(
            game_state=state, event=GameEvent.SKILL_VALUE_DETERMINED,
            investigator_id="inv1", skill_type=Skill.COMBAT, amount=2,
        )
        bus.emit(ctx)
        assert ctx.amount == 2

    def test_bonus_damage_channel(self, setup):
        """+1伤害经 ctx.extra["bonus_damage"] 通道汇入。"""
        state, bus, inv, inst, impl = setup
        impl.activate(state, "inv1")
        ctx = EventContext(
            game_state=state, event=GameEvent.SKILL_TEST_SUCCESSFUL,
            investigator_id="inv1", skill_type=Skill.COMBAT, success=True,
            source="inst_shriv",
        )
        bus.emit(ctx)
        assert ctx.extra["bonus_damage"] == 1

    def test_horror_on_bad_token(self, setup):
        state, bus, inv, inst, impl = setup
        impl.activate(state, "inv1")
        bus.emit(EventContext(
            game_state=state, event=GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="inv1", chaos_token=ChaosTokenType.TABLET,
            source="inst_shriv",
        ))
        assert inv.horror == 1

    def test_no_horror_on_good_token(self, setup):
        state, bus, inv, inst, impl = setup
        impl.activate(state, "inv1")
        bus.emit(EventContext(
            game_state=state, event=GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="inv1", chaos_token=ChaosTokenType.MINUS_2,
            source="inst_shriv",
        ))
        assert inv.horror == 0

    def test_armed_cleared_after_test(self, setup):
        state, bus, inv, inst, impl = setup
        impl.activate(state, "inv1")
        bus.emit(EventContext(
            game_state=state, event=GameEvent.SKILL_TEST_ENDS,
            investigator_id="inv1",
        ))
        ctx = EventContext(
            game_state=state, event=GameEvent.SKILL_VALUE_DETERMINED,
            investigator_id="inv1", skill_type=Skill.COMBAT, amount=2,
            source="inst_shriv",
        )
        bus.emit(ctx)
        assert ctx.amount == 2
