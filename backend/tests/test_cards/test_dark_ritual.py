"""Tests for Dark Ritual (Level 0)."""

import pytest
from backend.cards.rogue.dark_ritual_lv0 import DarkRitual
from backend.engine.event_bus import EventBus, EventContext
from backend.models.chaos import ChaosBag
from backend.models.enums import ChaosTokenType, GameEvent
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, ScenarioState,
)
from backend.tests.conftest import make_investigator_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()
    bag = ChaosBag()
    bag.seed(1)
    bag.tokens = [
        ChaosTokenType.CURSE, ChaosTokenType.CURSE, ChaosTokenType.CURSE,
        ChaosTokenType.ZERO, ChaosTokenType.PLUS_1,
    ]

    inv_data = make_investigator_data()
    state.card_database[inv_data.id] = inv_data
    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1",
    )
    inv.resources = 1
    state.investigators["inv1"] = inv

    impl = DarkRitual("dr_inst")
    impl.register(bus, "dr_inst")
    impl.bind_chaos_bag(bag)
    ci = CardInstance(
        instance_id="dr_inst", card_id="dark_ritual_lv0",
        owner_id="inv1", controller_id="inv1",
    )
    state.cards_in_play["dr_inst"] = ci
    inv.play_area.append("dr_inst")
    return state, bus, inv, impl, ci, bag


class TestDarkRitual:
    def test_seal_curses_on_enter(self, setup):
        """入场：封印袋中全部[诅咒]（至多5个）。"""
        state, bus, inv, impl, ci, bag = setup
        bus.emit(EventContext(
            game_state=state, event=GameEvent.CARD_ENTERS_PLAY,
            investigator_id="inv1", target="dr_inst",
            extra={"card_id": "dark_ritual_lv0"},
        ))
        assert len(impl._sealed) == 3
        assert ChaosTokenType.CURSE not in bag.tokens
        assert len(bag.sealed) == 3

    def test_mythos_end_spends_resource(self, setup):
        """神话阶段结束：有资源则花1资源维持。"""
        state, bus, inv, impl, ci, bag = setup
        bus.emit(EventContext(
            game_state=state, event=GameEvent.MYTHOS_PHASE_ENDS,
        ))
        assert inv.resources == 0
        assert state.get_card_instance("dr_inst") is not None

    def test_mythos_end_discards_when_broke(self, setup):
        """神话阶段结束：无资源则丢弃本卡，封印标记归还袋中。"""
        state, bus, inv, impl, ci, bag = setup
        bus.emit(EventContext(
            game_state=state, event=GameEvent.CARD_ENTERS_PLAY,
            investigator_id="inv1", target="dr_inst",
            extra={"card_id": "dark_ritual_lv0"},
        ))
        inv.resources = 0
        bus.emit(EventContext(
            game_state=state, event=GameEvent.MYTHOS_PHASE_ENDS,
        ))
        assert state.get_card_instance("dr_inst") is None
        assert "dr_inst" not in inv.play_area
        assert "dark_ritual_lv0" in inv.discard
        # 封印的诅咒归还袋中
        assert bag.tokens.count(ChaosTokenType.CURSE) == 3
        assert bag.sealed == []
