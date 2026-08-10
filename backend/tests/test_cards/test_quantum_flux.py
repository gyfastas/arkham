"""Tests for Quantum Flux (Level 0). (03196)

将弃牌堆洗入牌库并抽1张牌；从游戏中移除量子通量。
"""

import pytest
from backend.cards.mystic.quantum_flux_lv0 import QuantumFlux
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import Action, GameEvent
from backend.models.state import GameState, InvestigatorState, ScenarioState
from backend.tests.conftest import (
    make_asset_data, make_event_data, make_investigator_data,
)


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()

    inv_data = make_investigator_data()
    state.card_database[inv_data.id] = inv_data
    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1",
    )
    state.investigators["inv1"] = inv

    state.card_database["quantum_flux_lv0"] = make_event_data(
        id="quantum_flux_lv0", name="Quantum Flux", cost=1,
    )
    state.card_database["machete_lv0"] = make_asset_data(
        id="machete_lv0", name="Machete", traits=["item", "weapon"],
    )

    impl = QuantumFlux("inst_qf")
    impl.register(bus, "inst_qf")
    return state, bus, inv, impl


def _play(bus, state):
    ctx = EventContext(
        game_state=state, event=GameEvent.CARD_PLAYED,
        investigator_id="inv1", extra={"card_id": "quantum_flux_lv0"},
    )
    bus.emit(ctx)
    return ctx


class TestQuantumFlux:
    def test_shuffle_discard_into_deck_and_draw(self, setup):
        """弃牌堆洗入牌库，抽1张。"""
        state, bus, inv, impl = setup
        inv.deck = ["machete_lv0"]
        inv.discard = ["machete_lv0", "machete_lv0"]
        ctx = _play(bus, state)
        assert ctx.extra["quantum_flux_resolved"] is True
        assert ctx.extra["quantum_flux_drew"] is True
        assert inv.discard == []
        assert len(inv.hand) == 1  # 抽到1张
        assert len(inv.deck) == 2  # 3张洗入后抽走1张

    def test_removed_from_game_after_play_flow(self, setup):
        """打出流程中本卡后入弃牌堆：下一行动结算后移出游戏。"""
        state, bus, inv, impl = setup
        _play(bus, state)
        # 模拟 _play_event：结算后事件入弃牌堆
        inv.discard.append("quantum_flux_lv0")
        bus.emit(EventContext(
            game_state=state, event=GameEvent.ACTION_PERFORMED,
            investigator_id="inv1", action=Action.PLAY,
        ))
        assert "quantum_flux_lv0" not in inv.discard
        assert state.scenario.vars["removed_from_game"] == ["quantum_flux_lv0"]

    def test_removed_from_game_at_round_ends_fallback(self, setup):
        """回合结束兜底：仍在弃牌堆则移出游戏。"""
        state, bus, inv, impl = setup
        _play(bus, state)
        inv.discard.append("quantum_flux_lv0")
        bus.emit(EventContext(
            game_state=state, event=GameEvent.ROUND_ENDS,
        ))
        assert "quantum_flux_lv0" not in inv.discard
        assert "quantum_flux_lv0" in state.scenario.vars["removed_from_game"]

    def test_empty_discard_and_deck(self, setup):
        """空牌库空弃牌堆：不抽牌也不报错。"""
        state, bus, inv, impl = setup
        ctx = _play(bus, state)
        assert ctx.extra["quantum_flux_resolved"] is True
        assert "quantum_flux_drew" not in ctx.extra
        assert inv.hand == []
