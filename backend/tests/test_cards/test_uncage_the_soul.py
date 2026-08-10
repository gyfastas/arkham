"""Tests for Uncage the Soul (Level 0). (03033)

打出你手牌中一张法术/仪式卡，其资源费用降低3点。
"""

import pytest
from backend.cards.mystic.uncage_the_soul_lv0 import UncageTheSoul
from backend.engine.event_bus import EventBus, EventContext
from backend.engine.slots import SlotManager
from backend.models.enums import GameEvent, SlotType
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
        resources=2,
    )
    state.investigators["inv1"] = inv
    mgr = SlotManager()
    state.slot_managers = {"inv1": mgr}

    state.card_database["uncage_the_soul_lv0"] = make_event_data(
        id="uncage_the_soul_lv0", name="Uncage the Soul", cost=0,
    )
    state.card_database["shrivelling_lv0"] = make_asset_data(
        id="shrivelling_lv0", name="Shrivelling", cost=3,
        traits=["spell"], slots=[SlotType.ARCANE], uses={"charges": 4},
    )
    state.card_database["machete_lv0"] = make_asset_data(
        id="machete_lv0", name="Machete", cost=2, traits=["item", "weapon"],
    )
    state.card_database["blinding_light_lv0"] = make_event_data(
        id="blinding_light_lv0", name="Blinding Light", cost=1,
    )
    state.card_database["blinding_light_lv0"].traits = ["spell"]

    impl = UncageTheSoul("inst_uts")
    impl.register(bus, "inst_uts")
    return state, bus, inv, impl, mgr


def _play(bus, state, **extra):
    ctx = EventContext(
        game_state=state, event=GameEvent.CARD_PLAYED,
        investigator_id="inv1", extra={"card_id": "uncage_the_soul_lv0", **extra},
    )
    bus.emit(ctx)
    return ctx


class TestUncageTheSoul:
    def test_plays_spell_asset_with_3_discount(self, setup):
        """打出3费法术支援：只付0资源，进入场地并占用奥秘槽、初始化充能。"""
        state, bus, inv, impl, mgr = setup
        inv.hand = ["shrivelling_lv0"]
        ctx = _play(bus, state)
        assert ctx.extra["uncage_the_soul_played"] == "shrivelling_lv0"
        assert ctx.extra["uncage_the_soul_cost_paid"] == 0
        assert inv.resources == 2
        assert inv.hand == []
        iid = ctx.extra["uncage_the_soul_instance"]
        assert iid in inv.play_area
        inst = state.get_card_instance(iid)
        assert inst.uses["charges"] == 4
        assert mgr.available(SlotType.ARCANE) == 1  # 2槽占1

    def test_discount_partial(self, setup):
        """5费法术（模拟）：付2资源。"""
        state, bus, inv, impl, mgr = setup
        state.card_database["big_spell"] = make_asset_data(
            id="big_spell", name="Big Spell", cost=5, traits=["spell"],
        )
        inv.hand = ["big_spell"]
        ctx = _play(bus, state)
        assert ctx.extra["uncage_the_soul_cost_paid"] == 2
        assert inv.resources == 0

    def test_auto_targets_first_spell_in_hand(self, setup):
        """无指定时自动选手牌中第一张法术/仪式（跳过非法术）。"""
        state, bus, inv, impl, mgr = setup
        inv.hand = ["machete_lv0", "shrivelling_lv0"]
        ctx = _play(bus, state)
        assert ctx.extra["uncage_the_soul_played"] == "shrivelling_lv0"
        assert inv.hand == ["machete_lv0"]

    def test_non_spell_rejected(self, setup):
        """手牌中没有法术/仪式时不生效（不扣资源）。"""
        state, bus, inv, impl, mgr = setup
        inv.hand = ["machete_lv0"]
        ctx = _play(bus, state)
        assert "uncage_the_soul_played" not in ctx.extra
        assert inv.resources == 2
        assert inv.hand == ["machete_lv0"]

    def test_spell_event_goes_to_discard(self, setup):
        """法术事件：减费打出但不自动结算效果，入弃牌堆（引擎缺口）。"""
        state, bus, inv, impl, mgr = setup
        inv.hand = ["blinding_light_lv0"]
        ctx = _play(bus, state)
        assert ctx.extra["uncage_the_soul_played"] == "blinding_light_lv0"
        assert ctx.extra["uncage_the_soul_cost_paid"] == 0
        assert inv.discard == ["blinding_light_lv0"]

    def test_fails_when_cannot_afford_reduced_cost(self, setup):
        state, bus, inv, impl, mgr = setup
        state.card_database["big_spell"] = make_asset_data(
            id="big_spell", name="Big Spell", cost=6, traits=["spell"],
        )
        inv.hand = ["big_spell"]
        inv.resources = 2  # 减后仍需3，付不起
        ctx = _play(bus, state)
        assert "uncage_the_soul_played" not in ctx.extra
        assert inv.hand == ["big_spell"]
        assert inv.resources == 2
