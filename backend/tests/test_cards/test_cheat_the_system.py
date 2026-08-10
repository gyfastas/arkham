"""Tests for Cheat the System (Level 1)."""

import pytest
from backend.cards.rogue.cheat_the_system_lv1 import CheatTheSystem
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent, PlayerClass
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, ScenarioState,
)
from backend.tests.conftest import make_asset_data, make_investigator_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()
    inv_data = make_investigator_data()
    state.card_database[inv_data.id] = inv_data
    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1",
    )
    inv.resources = 3
    state.investigators["inv1"] = inv

    for cid, pclass in [
        ("asset_g", PlayerClass.GUARDIAN),
        ("asset_m", PlayerClass.MYSTIC),
        ("asset_r1", PlayerClass.ROGUE),
        ("asset_r2", PlayerClass.ROGUE),
    ]:
        state.card_database[cid] = make_asset_data(
            id=cid, name=cid, card_class=pclass)

    impl = CheatTheSystem("cts_inst")
    impl.register(bus, "cts_inst")
    return state, bus, inv, impl


def _put_in_play(state, inv, card_id, instance_id):
    state.cards_in_play[instance_id] = CardInstance(
        instance_id=instance_id, card_id=card_id,
        owner_id="inv1", controller_id="inv1",
    )
    inv.play_area.append(instance_id)


class TestCheatTheSystem:
    def test_gain_per_distinct_class(self, setup):
        """3个不同职阶（守护者/秘法师/流浪者×2）→ +3资源。"""
        state, bus, inv, impl = setup
        _put_in_play(state, inv, "asset_g", "i1")
        _put_in_play(state, inv, "asset_m", "i2")
        _put_in_play(state, inv, "asset_r1", "i3")
        _put_in_play(state, inv, "asset_r2", "i4")

        ctx = EventContext(
            game_state=state, event=GameEvent.CARD_PLAYED,
            investigator_id="inv1", extra={"card_id": "cheat_the_system_lv1"},
        )
        bus.emit(ctx)
        assert inv.resources == 6
        assert ctx.extra["cheat_the_system_classes"] == 3

    def test_no_assets_no_gain(self, setup):
        state, bus, inv, impl = setup
        ctx = EventContext(
            game_state=state, event=GameEvent.CARD_PLAYED,
            investigator_id="inv1", extra={"card_id": "cheat_the_system_lv1"},
        )
        bus.emit(ctx)
        assert inv.resources == 3

    def test_single_class(self, setup):
        state, bus, inv, impl = setup
        _put_in_play(state, inv, "asset_r1", "i1")
        ctx = EventContext(
            game_state=state, event=GameEvent.CARD_PLAYED,
            investigator_id="inv1", extra={"card_id": "cheat_the_system_lv1"},
        )
        bus.emit(ctx)
        assert inv.resources == 4
