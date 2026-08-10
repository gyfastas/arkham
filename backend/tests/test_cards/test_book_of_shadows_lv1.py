"""Tests for Book of Shadows (Level 1). (03154)

【行动】横置+1资源：给你控制的一张法术支援卡添加1个充能（无奥秘槽加成）。
"""

import pytest
from backend.cards.mystic.book_of_shadows_lv1 import BookOfShadowsLv1
from backend.engine.event_bus import EventBus, EventContext
from backend.engine.slots import SlotManager
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
        resources=3,
    )
    state.investigators["inv1"] = inv
    mgr = SlotManager()
    state.slot_managers = {"inv1": mgr}

    state.card_database["book_of_shadows_lv1"] = make_asset_data(
        id="book_of_shadows_lv1", name="Book of Shadows", cost=3,
        traits=["item", "tome"], slots=[SlotType.HAND],
    )
    state.card_database["shrivelling_lv0"] = make_asset_data(
        id="shrivelling_lv0", name="Shrivelling", traits=["spell"],
        slots=[SlotType.ARCANE],
    )

    inst = CardInstance(
        instance_id="inst_bos", card_id="book_of_shadows_lv1",
        owner_id="inv1", controller_id="inv1",
    )
    state.cards_in_play["inst_bos"] = inst
    inv.play_area.append("inst_bos")

    impl = BookOfShadowsLv1("inst_bos")
    impl.register(bus, "inst_bos")
    return state, bus, inv, inst, impl, mgr


def _add_spell(state, inv, charges=1):
    spell = CardInstance(
        instance_id="inst_shriv", card_id="shrivelling_lv0",
        owner_id="inv1", controller_id="inv1",
    )
    spell.uses = {"charges": charges}
    state.cards_in_play["inst_shriv"] = spell
    inv.play_area.append("inst_shriv")
    return spell


class TestBookOfShadowsLv1:
    def test_no_arcane_slot_bonus(self, setup):
        """lv1 不提供额外奥秘槽（那是 lv3 的效果）。"""
        state, bus, inv, inst, impl, mgr = setup
        base = mgr.available(SlotType.ARCANE)
        bus.emit(EventContext(
            game_state=state, event=GameEvent.CARD_ENTERS_PLAY,
            investigator_id="inv1", target="inst_bos",
        ))
        assert mgr.available(SlotType.ARCANE) == base

    def test_activate_costs_resource_and_adds_charge(self, setup):
        """横置+1资源：法术支援+1充能。"""
        state, bus, inv, inst, impl, mgr = setup
        spell = _add_spell(state, inv, charges=1)
        assert impl.activate(state, "inv1") is True
        assert inst.exhausted is True
        assert inv.resources == 2
        assert spell.uses["charges"] == 2

    def test_activate_fails_without_resource(self, setup):
        state, bus, inv, inst, impl, mgr = setup
        spell = _add_spell(state, inv, charges=1)
        inv.resources = 0
        assert impl.activate(state, "inv1") is False
        assert inst.exhausted is False
        assert spell.uses["charges"] == 1

    def test_activate_fails_without_spell_target(self, setup):
        """没有带充能的法术支援时无法发动，不扣资源。"""
        state, bus, inv, inst, impl, mgr = setup
        assert impl.activate(state, "inv1") is False
        assert inv.resources == 3
        assert inst.exhausted is False
