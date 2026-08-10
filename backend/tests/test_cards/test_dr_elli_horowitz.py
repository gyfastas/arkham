"""Tests for Dr. Elli Horowitz (Level 0). (04021)

入场后：检索牌堆顶9张，第一张圣物附着到她身上（不占栏位），混洗牌堆。
"""

import pytest

from backend.cards.seeker.dr_elli_horowitz_lv0 import DrElliHorowitz
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent, SlotType
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
    state.investigators["inv1"] = inv

    for cid, traits in [
        ("a1", []), ("a2", []), ("relic_stone", ["item", "relic"]),
        ("a3", []), ("a4", []),
    ]:
        state.card_database[cid] = make_asset_data(
            id=cid, name=cid, traits=traits, slots=[SlotType.HAND])
    inv.deck = ["a1", "a2", "relic_stone", "a3", "a4"]

    state.card_database["dr_elli_horowitz_lv0"] = make_asset_data(
        id="dr_elli_horowitz_lv0", name="Dr. Elli Horowitz",
        slots=[SlotType.ALLY], traits=["ally", "assistant"])
    elli = CardInstance(
        instance_id="inst_elli", card_id="dr_elli_horowitz_lv0",
        owner_id="inv1", controller_id="inv1", slot_used=[SlotType.ALLY],
    )
    state.cards_in_play["inst_elli"] = elli
    inv.play_area.append("inst_elli")

    impl = DrElliHorowitz("inst_elli")
    impl.register(bus, "inst_elli")
    return state, bus, inv, impl


class TestDrElliHorowitz:
    def test_enters_play_attaches_first_relic(self, setup):
        """顶9张中的第一张圣物附着入场：不占栏位、仍在场由你控制。"""
        state, bus, inv, impl = setup
        ctx = EventContext(
            game_state=state, event=GameEvent.CARD_ENTERS_PLAY,
            investigator_id="inv1", target="inst_elli",
        )
        bus.emit(ctx)
        assert ctx.extra.get("elli_attached_relic") == "relic_stone"
        relic = next(
            ci for ci in state.cards_in_play.values()
            if ci.card_id == "relic_stone"
        )
        assert relic.instance_id in inv.play_area
        assert relic.attached_to == "inst_elli"
        assert relic.slot_used == []  # 不占任何栏位
        # 牌堆洗混后仍是4张且不含圣物
        assert len(inv.deck) == 4
        assert "relic_stone" not in inv.deck
        assert sorted(inv.deck) == ["a1", "a2", "a3", "a4"]

    def test_no_relic_in_top9_only_shuffles(self, setup):
        state, bus, inv, impl = setup
        inv.deck = ["a1", "a2", "a3", "a4"]
        ctx = EventContext(
            game_state=state, event=GameEvent.CARD_ENTERS_PLAY,
            investigator_id="inv1", target="inst_elli",
        )
        bus.emit(ctx)
        assert "elli_attached_relic" not in ctx.extra
        assert len(state.cards_in_play) == 1
        assert len(inv.deck) == 4
