"""Tests for Deny Existence (Level 0 / Level 5). (05032/05280)

快速（0费）：你将被分配伤害/恐惧时自动从手牌打出，忽略该方面；
lv5 再执行相反效果（治愈等量伤害/恐惧）。
"""

import pytest
from backend.cards.mystic.deny_existence_lv0 import DenyExistence
from backend.cards.mystic.deny_existence_lv5 import DenyExistenceLv5
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent
from backend.models.state import GameState, InvestigatorState, ScenarioState
from backend.tests.conftest import make_event_data, make_investigator_data


def _make(card_id, impl_cls):
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()
    inv_data = make_investigator_data()
    state.card_database[inv_data.id] = inv_data
    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1",
        resources=0, hand=[card_id],
    )
    state.investigators["inv1"] = inv
    state.card_database[card_id] = make_event_data(id=card_id, name="Deny", cost=0)
    impl = impl_cls(f"impl_{card_id}")
    impl.register(bus, f"impl_{card_id}")
    return state, bus, inv, impl


class TestDenyExistenceLv0:
    def test_cancels_damage_assignment(self):
        """被分配2伤害：自动打出（0费）并取消。"""
        state, bus, inv, impl = _make("deny_existence_lv0", DenyExistence)
        ctx = EventContext(
            game_state=state, event=GameEvent.DAMAGE_ASSIGNED,
            investigator_id="inv1", amount=2, source="enemy_1",
        )
        bus.emit(ctx)
        assert ctx.cancelled is True
        assert ctx.extra["deny_existence_lv0_ignored_damage"] == 2
        assert "deny_existence_lv0" in inv.discard
        assert inv.hand == []

    def test_cancels_horror_assignment(self):
        state, bus, inv, impl = _make("deny_existence_lv0", DenyExistence)
        ctx = EventContext(
            game_state=state, event=GameEvent.HORROR_ASSIGNED,
            investigator_id="inv1", amount=1,
        )
        bus.emit(ctx)
        assert ctx.cancelled is True

    def test_single_aspect_only(self):
        """一张否决存在只忽略一个方面：第二次分配不再取消。"""
        state, bus, inv, impl = _make("deny_existence_lv0", DenyExistence)
        bus.emit(EventContext(
            game_state=state, event=GameEvent.DAMAGE_ASSIGNED,
            investigator_id="inv1", amount=1,
        ))
        ctx2 = EventContext(
            game_state=state, event=GameEvent.HORROR_ASSIGNED,
            investigator_id="inv1", amount=1,
        )
        bus.emit(ctx2)
        assert ctx2.cancelled is False


class TestDenyExistenceLv5:
    def test_cancels_and_heals_damage(self):
        """lv5：忽略2伤害并治愈2伤害。"""
        state, bus, inv, impl = _make("deny_existence_lv5", DenyExistenceLv5)
        inv.damage = 3
        ctx = EventContext(
            game_state=state, event=GameEvent.DAMAGE_ASSIGNED,
            investigator_id="inv1", amount=2,
        )
        bus.emit(ctx)
        assert ctx.cancelled is True
        assert inv.damage == 1  # 3 - 2
        assert ctx.extra["deny_existence_lv5_reversed_damage"] == 2

    def test_cancels_and_heals_horror(self):
        state, bus, inv, impl = _make("deny_existence_lv5", DenyExistenceLv5)
        inv.horror = 2
        ctx = EventContext(
            game_state=state, event=GameEvent.HORROR_ASSIGNED,
            investigator_id="inv1", amount=2,
        )
        bus.emit(ctx)
        assert ctx.cancelled is True
        assert inv.horror == 0

    def test_no_heal_without_reverse_on_lv0(self):
        """lv0 不治愈（对照）。"""
        state, bus, inv, impl = _make("deny_existence_lv0", DenyExistence)
        inv.horror = 2
        bus.emit(EventContext(
            game_state=state, event=GameEvent.HORROR_ASSIGNED,
            investigator_id="inv1", amount=1,
        ))
        assert inv.horror == 2
