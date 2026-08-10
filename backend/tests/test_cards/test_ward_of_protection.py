"""Tests for Ward of Protection (Level 0). (01065)

快速。抽取非弱点诡计卡时打出：取消该卡的揭示效果，然后受1恐惧。
（简化：自动强制打出，不可选不打出。）
"""

import pytest
from backend.cards.mystic.ward_of_protection_lv0 import WardOfProtection
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import CardType, GameEvent
from backend.models.state import (
    CardData, GameState, InvestigatorState, ScenarioState,
)
from backend.tests.conftest import make_event_data, make_investigator_data
from backend.models.enums import PlayerClass


def _treachery(id: str, subtype: str = "") -> CardData:
    return CardData(
        id=id, name=id, name_cn=id, type=CardType.TREACHERY,
        card_class=PlayerClass.NEUTRAL, subtype=subtype,
    )


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()

    inv_data = make_investigator_data()
    state.card_database[inv_data.id] = inv_data
    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1",
        resources=3, hand=["ward_of_protection_lv0"],
    )
    state.investigators["inv1"] = inv

    state.card_database["ward_of_protection_lv0"] = make_event_data(
        id="ward_of_protection_lv0", name="Ward of Protection", cost=1,
    )
    state.card_database["frozen_in_fear"] = _treachery("frozen_in_fear")
    state.card_database["dark_memory"] = _treachery("dark_memory", subtype="weakness")

    impl = WardOfProtection("inst_wop")
    impl.register(bus, "inst_wop")
    return state, bus, inv, impl


def _draw_encounter(state, bus, card_id):
    ctx = EventContext(
        game_state=state, event=GameEvent.ENCOUNTER_CARD_DRAWN,
        investigator_id="inv1", extra={"card_id": card_id},
    )
    bus.emit(ctx)
    return ctx


class TestWardOfProtection:
    def test_cancels_non_weakness_treachery(self, setup):
        """自动打出：付费、受1恐惧、标记取消、入弃牌堆。"""
        state, bus, inv, impl = setup
        ctx = _draw_encounter(state, bus, "frozen_in_fear")
        assert ctx.extra["ward_of_protection_cancelled"] == "frozen_in_fear"
        assert state.scenario.vars["cancelled_encounter"] == "frozen_in_fear"
        assert inv.resources == 2
        assert inv.horror == 1
        assert "ward_of_protection_lv0" not in inv.hand
        assert "ward_of_protection_lv0" in inv.discard

    def test_ignores_weakness_treachery(self, setup):
        state, bus, inv, impl = setup
        ctx = _draw_encounter(state, bus, "dark_memory")
        assert "ward_of_protection_cancelled" not in ctx.extra
        assert "ward_of_protection_lv0" in inv.hand
        assert inv.horror == 0

    def test_ignores_enemy_cards(self, setup):
        state, bus, inv, impl = setup
        from backend.tests.conftest import make_enemy_data
        state.card_database["ghoul"] = make_enemy_data(id="ghoul")
        ctx = _draw_encounter(state, bus, "ghoul")
        assert "ward_of_protection_cancelled" not in ctx.extra

    def test_no_cancel_without_resources(self, setup):
        state, bus, inv, impl = setup
        inv.resources = 0
        ctx = _draw_encounter(state, bus, "frozen_in_fear")
        assert "ward_of_protection_cancelled" not in ctx.extra
        assert "ward_of_protection_lv0" in inv.hand
