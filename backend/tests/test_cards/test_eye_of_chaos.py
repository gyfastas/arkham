"""Tests for Eye of Chaos (Level 0 / Level 4).

花1充能：用意志调查；成功额外+1线索；揭示[curse]时发现连接地点线索或放充能。
lv4：+2意志，且每个[curse]各结算一次奖励。
"""

import pytest
from backend.cards.mystic.eye_of_chaos_lv0 import EyeOfChaos
from backend.cards.mystic.eye_of_chaos_lv4 import EyeOfChaosLv4
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import ChaosTokenType, GameEvent, Skill
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, LocationState, ScenarioState,
)
from backend.tests.conftest import make_asset_data, make_investigator_data, make_location_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()
    inv_data = make_investigator_data(willpower=5, intellect=2)
    state.card_database[inv_data.id] = inv_data
    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1")
    state.investigators["inv1"] = inv

    for loc_id, clues, conns in (("loc1", 2, ["loc2"]), ("loc2", 1, ["loc1"])):
        ld = make_location_data(id=loc_id, connections=conns)
        state.card_database[loc_id] = ld
        state.locations[loc_id] = LocationState(
            location_id=loc_id, card_data=ld, clues=clues)

    state.card_database["eye_of_chaos_lv0"] = make_asset_data(
        id="eye_of_chaos_lv0", name="Eye of Chaos", traits=["spell", "cursed"],
        uses={"charges": 3})
    inst = CardInstance(
        instance_id="inst_eoc", card_id="eye_of_chaos_lv0",
        owner_id="inv1", controller_id="inv1")
    inst.uses = {"charges": 3}
    state.cards_in_play["inst_eoc"] = inst
    inv.play_area.append("inst_eoc")

    impl = EyeOfChaos("inst_eoc")
    impl.register(bus, "inst_eoc")
    return state, bus, inv, inst, impl


class TestEyeOfChaosLv0:
    def test_activate_spends_charge(self, setup):
        state, bus, inv, inst, impl = setup
        assert impl.activate(state, "inv1") is True
        assert inst.uses["charges"] == 2

    def test_willpower_substitute(self, setup):
        """意志(5)代替智力(2)，lv0 无额外加值。"""
        state, bus, inv, inst, impl = setup
        impl.activate(state, "inv1")
        ctx = EventContext(
            game_state=state, event=GameEvent.SKILL_VALUE_DETERMINED,
            investigator_id="inv1", skill_type=Skill.INTELLECT, amount=2)
        bus.emit(ctx)
        assert ctx.amount == 5

    def test_success_extra_clue(self, setup):
        state, bus, inv, inst, impl = setup
        impl.activate(state, "inv1")
        ctx = EventContext(
            game_state=state, event=GameEvent.CLUE_DISCOVERED,
            investigator_id="inv1", location_id="loc1", amount=1)
        bus.emit(ctx)
        assert state.locations["loc1"].clues == 1
        assert inv.clues == 1
        assert ctx.extra["eye_of_chaos_lv0_extra_clue"] is True

    def test_curse_reward_prefers_connecting_clue(self, setup):
        """揭示[curse]：自动发现连接地点(loc2)的1线索。"""
        state, bus, inv, inst, impl = setup
        impl.activate(state, "inv1")
        bus.emit(EventContext(
            game_state=state, event=GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="inv1", chaos_token=ChaosTokenType.CURSE))
        ctx = EventContext(
            game_state=state, event=GameEvent.SKILL_TEST_ENDS,
            investigator_id="inv1")
        bus.emit(ctx)
        assert state.locations["loc2"].clues == 0
        assert inv.clues == 1
        assert ctx.extra["eye_of_chaos_lv0_connecting_clue"] == "loc2"

    def test_curse_reward_places_charge_when_no_clue(self, setup):
        """连接地点无线索：改为在混沌之眼上放1充能。"""
        state, bus, inv, inst, impl = setup
        state.locations["loc2"].clues = 0
        impl.activate(state, "inv1")
        bus.emit(EventContext(
            game_state=state, event=GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="inv1", chaos_token=ChaosTokenType.CURSE))
        bus.emit(EventContext(
            game_state=state, event=GameEvent.SKILL_TEST_ENDS,
            investigator_id="inv1"))
        assert inst.uses["charges"] == 3  # 2 remaining + 1 placed


class TestEyeOfChaosLv4:
    def test_lv4_bonus_and_per_curse(self, setup):
        state, bus, inv, inst, _ = setup
        state.card_database["eye_of_chaos_lv4"] = make_asset_data(
            id="eye_of_chaos_lv4", name="Eye of Chaos",
            traits=["spell", "cursed"], uses={"charges": 3})
        inst4 = CardInstance(
            instance_id="inst_eoc4", card_id="eye_of_chaos_lv4",
            owner_id="inv1", controller_id="inv1")
        inst4.uses = {"charges": 3}
        state.cards_in_play["inst_eoc4"] = inst4
        inv.play_area.append("inst_eoc4")
        impl4 = EyeOfChaosLv4("inst_eoc4")
        impl4.register(bus, "inst_eoc4")

        impl4.activate(state, "inv1")
        ctx = EventContext(
            game_state=state, event=GameEvent.SKILL_VALUE_DETERMINED,
            investigator_id="inv1", skill_type=Skill.INTELLECT, amount=2)
        bus.emit(ctx)
        assert ctx.amount == 7  # 意志5 + lv4加值2

        # 每个[curse]各结算一次：两个[curse] → loc2线索 + 充能
        for _ in range(2):
            bus.emit(EventContext(
                game_state=state, event=GameEvent.CHAOS_TOKEN_RESOLVED,
                investigator_id="inv1", chaos_token=ChaosTokenType.CURSE))
        bus.emit(EventContext(
            game_state=state, event=GameEvent.SKILL_TEST_ENDS,
            investigator_id="inv1"))
        assert state.locations["loc2"].clues == 0
        assert inv.clues == 1
        assert inst4.uses["charges"] == 3  # 第二次奖励无线索可取 → 放充能
