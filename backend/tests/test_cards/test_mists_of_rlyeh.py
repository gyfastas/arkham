"""Tests for Mists of R'lyeh (Level 0 / Level 4).

花1充能：用意志躲避；成功后可移动到连接地点（简化：自动移首个连接地点）；
坏标记弃手牌最后1张。lv4：+3意志。
"""

import pytest
from backend.cards.mystic.mists_of_rlyeh_lv0 import MistsOfRlyeh
from backend.cards.mystic.mists_of_rlyeh_lv4 import MistsOfRlyehLv4
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
    inv_data = make_investigator_data(willpower=5, agility=2)
    state.card_database[inv_data.id] = inv_data
    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1",
        hand=["card_a", "card_b"])
    state.investigators["inv1"] = inv

    for loc_id, conns in (("loc1", ["loc2"]), ("loc2", ["loc1"])):
        ld = make_location_data(id=loc_id, connections=conns)
        state.card_database[loc_id] = ld
        state.locations[loc_id] = LocationState(location_id=loc_id, card_data=ld)

    state.card_database["mists_of_rlyeh_lv0"] = make_asset_data(
        id="mists_of_rlyeh_lv0", name="Mists of R'lyeh", traits=["spell"],
        uses={"charges": 4})
    inst = CardInstance(
        instance_id="inst_mists", card_id="mists_of_rlyeh_lv0",
        owner_id="inv1", controller_id="inv1")
    inst.uses = {"charges": 4}
    state.cards_in_play["inst_mists"] = inst
    inv.play_area.append("inst_mists")

    impl = MistsOfRlyeh("inst_mists")
    impl.register(bus, "inst_mists")
    return state, bus, inv, inst, impl


class TestMistsOfRlyehLv0:
    def test_activate_spends_charge(self, setup):
        state, bus, inv, inst, impl = setup
        assert impl.activate(state, "inv1") is True
        assert inst.uses["charges"] == 3

    def test_willpower_substitute(self, setup):
        state, bus, inv, inst, impl = setup
        impl.activate(state, "inv1")
        ctx = EventContext(
            game_state=state, event=GameEvent.SKILL_VALUE_DETERMINED,
            investigator_id="inv1", skill_type=Skill.AGILITY, amount=2)
        bus.emit(ctx)
        assert ctx.amount == 5

    def test_move_after_successful_evade(self, setup):
        state, bus, inv, inst, impl = setup
        impl.activate(state, "inv1")
        ctx = EventContext(
            game_state=state, event=GameEvent.ENEMY_EVADED,
            investigator_id="inv1", enemy_id="enemy_1")
        bus.emit(ctx)
        assert inv.location_id == "loc2"
        assert ctx.extra["mists_of_rlyeh_lv0_moved_to"] == "loc2"

    def test_bad_token_discards_card(self, setup):
        state, bus, inv, inst, impl = setup
        impl.activate(state, "inv1")
        bus.emit(EventContext(
            game_state=state, event=GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="inv1", chaos_token=ChaosTokenType.SKULL))
        ctx = EventContext(
            game_state=state, event=GameEvent.SKILL_TEST_ENDS,
            investigator_id="inv1")
        bus.emit(ctx)
        assert inv.hand == ["card_a"]
        assert inv.discard == ["card_b"]
        assert ctx.extra["mists_of_rlyeh_lv0_discarded"] == "card_b"

    def test_no_discard_on_good_token(self, setup):
        state, bus, inv, inst, impl = setup
        impl.activate(state, "inv1")
        bus.emit(EventContext(
            game_state=state, event=GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="inv1", chaos_token=ChaosTokenType.ZERO))
        bus.emit(EventContext(
            game_state=state, event=GameEvent.SKILL_TEST_ENDS,
            investigator_id="inv1"))
        assert inv.hand == ["card_a", "card_b"]


class TestMistsOfRlyehLv4:
    def test_lv4_plus3_willpower(self, setup):
        state, bus, inv, inst, _ = setup
        state.card_database["mists_of_rlyeh_lv4"] = make_asset_data(
            id="mists_of_rlyeh_lv4", name="Mists of R'lyeh", traits=["spell"],
            uses={"charges": 5})
        inst4 = CardInstance(
            instance_id="inst_mists4", card_id="mists_of_rlyeh_lv4",
            owner_id="inv1", controller_id="inv1")
        inst4.uses = {"charges": 5}
        state.cards_in_play["inst_mists4"] = inst4
        inv.play_area.append("inst_mists4")
        impl4 = MistsOfRlyehLv4("inst_mists4")
        impl4.register(bus, "inst_mists4")

        impl4.activate(state, "inv1")
        assert inst4.uses["charges"] == 4
        ctx = EventContext(
            game_state=state, event=GameEvent.SKILL_VALUE_DETERMINED,
            investigator_id="inv1", skill_type=Skill.AGILITY, amount=2)
        bus.emit(ctx)
        assert ctx.amount == 8  # 意志5 + lv4加值3
