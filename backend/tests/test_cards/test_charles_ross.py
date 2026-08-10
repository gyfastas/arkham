"""Tests for Charles Ross, Esq. (Level 0).

官方：[快速]横置：你所在地点的调查员打出的下一张[[Item]]支援费用-1。
（实现为入场后返还1资源。）
"""

import pytest

from backend.cards.seeker.charles_ross_esq_lv0 import CharlesRossEsq
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, LocationState, ScenarioState,
)
from backend.tests.conftest import (
    make_asset_data, make_investigator_data, make_location_data,
)


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()

    inv_data = make_investigator_data()
    state.card_database[inv_data.id] = inv_data
    loc_data = make_location_data(id="loc_a")
    state.card_database[loc_data.id] = loc_data
    state.locations["loc_a"] = LocationState(
        location_id="loc_a", card_data=loc_data)

    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc_a",
        resources=1,
    )
    state.investigators["inv1"] = inv

    state.card_database["charles_ross_esq_lv0"] = make_asset_data(
        id="charles_ross_esq_lv0", name="Charles Ross, Esq.", cost=2,
        traits=["ally", "patron"], health=1, sanity=2,
    )
    state.card_database["flashlight_lv0"] = make_asset_data(
        id="flashlight_lv0", name="Flashlight", cost=2, traits=["item"])
    state.card_database["beat_cop_lv0"] = make_asset_data(
        id="beat_cop_lv0", name="Beat Cop", cost=4, traits=["ally"])

    inst = CardInstance(
        instance_id="inst_ross", card_id="charles_ross_esq_lv0",
        owner_id="inv1", controller_id="inv1",
    )
    state.cards_in_play["inst_ross"] = inst
    inv.play_area.append("inst_ross")

    impl = CharlesRossEsq("inst_ross")
    impl.register(bus, "inst_ross")
    return state, bus, inv, inst, impl


def _asset_enters_play(state, bus, card_id, investigator_id="inv1"):
    ctx = EventContext(
        game_state=state,
        event=GameEvent.CARD_ENTERS_PLAY,
        investigator_id=investigator_id,
        target=f"inst_{card_id}",
        extra={"card_id": card_id},
    )
    bus.emit(ctx)
    return ctx


class TestCharlesRoss:
    def test_activate_exhausts_and_arms(self, setup):
        state, bus, inv, inst, impl = setup
        assert impl.activate(state, "inv1") is True
        assert inst.exhausted is True

    def test_next_item_asset_discounted(self, setup):
        """本地点道具支援入场：返还1资源。"""
        state, bus, inv, inst, impl = setup
        impl.activate(state, "inv1")
        ctx = _asset_enters_play(state, bus, "flashlight_lv0")
        assert inv.resources == 2
        assert ctx.extra.get("charles_ross_discount") is True

    def test_non_item_asset_not_discounted(self, setup):
        state, bus, inv, inst, impl = setup
        impl.activate(state, "inv1")
        _asset_enters_play(state, bus, "beat_cop_lv0")  # ally，非item
        assert inv.resources == 1

    def test_discount_consumed_once(self, setup):
        """折扣只对下一张道具生效一次。"""
        state, bus, inv, inst, impl = setup
        impl.activate(state, "inv1")
        _asset_enters_play(state, bus, "flashlight_lv0")
        _asset_enters_play(state, bus, "flashlight_lv0")
        assert inv.resources == 2  # 仅返还1次

    def test_other_location_not_discounted(self, setup):
        """不在罗斯所在地点的调查员打出道具：不返还。"""
        state, bus, inv, inst, impl = setup
        other_data = make_investigator_data(id="inv2_data")
        state.card_database[other_data.id] = other_data
        other = InvestigatorState(
            investigator_id="inv2", card_data=other_data,
            location_id="loc_elsewhere", resources=1,
        )
        state.investigators["inv2"] = other

        impl.activate(state, "inv1")
        _asset_enters_play(state, bus, "flashlight_lv0",
                           investigator_id="inv2")
        assert other.resources == 1

    def test_cannot_activate_while_exhausted(self, setup):
        state, bus, inv, inst, impl = setup
        inst.exhausted = True
        assert impl.activate(state, "inv1") is False
