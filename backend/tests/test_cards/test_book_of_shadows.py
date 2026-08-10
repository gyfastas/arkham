"""Tests for Book of Shadows (Level 3). (01070)

+1奥秘槽位；【行动】横置：给你控制的一张法术支援卡添加1个充能。
"""

import pytest
from backend.cards.mystic.book_of_shadows_lv3 import BookOfShadows
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
    )
    state.investigators["inv1"] = inv
    mgr = SlotManager()
    state.slot_managers = {"inv1": mgr}

    state.card_database["book_of_shadows_lv3"] = make_asset_data(
        id="book_of_shadows_lv3", name="Book of Shadows",
        traits=["item", "tome"], slots=[SlotType.HAND],
    )
    state.card_database["shrivelling_lv0"] = make_asset_data(
        id="shrivelling_lv0", name="Shrivelling", traits=["spell"],
        slots=[SlotType.ARCANE],
    )
    state.card_database["machete_lv0"] = make_asset_data(
        id="machete_lv0", name="Machete", traits=["item", "weapon"],
        slots=[SlotType.HAND],
    )

    inst = CardInstance(
        instance_id="inst_bos", card_id="book_of_shadows_lv3",
        owner_id="inv1", controller_id="inv1",
    )
    state.cards_in_play["inst_bos"] = inst
    inv.play_area.append("inst_bos")

    impl = BookOfShadows("inst_bos")
    impl.register(bus, "inst_bos")
    return state, bus, inv, inst, impl, mgr


def _add_spell(state, inv, instance_id="inst_shriv", charges=2):
    spell = CardInstance(
        instance_id=instance_id, card_id="shrivelling_lv0",
        owner_id="inv1", controller_id="inv1",
    )
    spell.uses = {"charges": charges}
    state.cards_in_play[instance_id] = spell
    inv.play_area.append(instance_id)
    return spell


class TestBookOfShadows:
    def test_arcane_slot_bonus_on_enter_and_leave(self, setup):
        """进场+1奥秘槽，离场移除。"""
        state, bus, inv, inst, impl, mgr = setup
        base = mgr.available(SlotType.ARCANE)
        bus.emit(EventContext(
            game_state=state, event=GameEvent.CARD_ENTERS_PLAY,
            investigator_id="inv1", target="inst_bos",
        ))
        assert mgr.available(SlotType.ARCANE) == base + 1
        bus.emit(EventContext(
            game_state=state, event=GameEvent.CARD_LEAVES_PLAY,
            investigator_id="inv1", target="inst_bos",
        ))
        assert mgr.available(SlotType.ARCANE) == base

    def test_no_skill_bonus(self, setup):
        """旧实现的"每控制一张法术+1意志+1智力"为编造，已删除。"""
        state, bus, inv, inst, impl, mgr = setup
        _add_spell(state, inv)
        from backend.models.enums import Skill
        ctx = EventContext(
            game_state=state, event=GameEvent.SKILL_VALUE_DETERMINED,
            investigator_id="inv1", skill_type=Skill.WILLPOWER, amount=3,
        )
        bus.emit(ctx)
        assert ctx.amount == 3

    def test_activate_adds_charge_and_exhausts(self, setup):
        """横置：给你控制的一张法术支援加1充能。"""
        state, bus, inv, inst, impl, mgr = setup
        spell = _add_spell(state, inv, charges=2)
        assert impl.activate(state, "inv1") is True
        assert inst.exhausted is True
        assert spell.uses["charges"] == 3

    def test_activate_requires_spell_target(self, setup):
        """没有带充能的法术支援时无法发动（非法术卡不算）。"""
        state, bus, inv, inst, impl, mgr = setup
        weapon = CardInstance(
            instance_id="inst_mach", card_id="machete_lv0",
            owner_id="inv1", controller_id="inv1",
        )
        state.cards_in_play["inst_mach"] = weapon
        inv.play_area.append("inst_mach")
        assert impl.activate(state, "inv1") is False
        assert inst.exhausted is False

    def test_activate_cannot_repeat_while_exhausted(self, setup):
        state, bus, inv, inst, impl, mgr = setup
        spell = _add_spell(state, inv, charges=1)
        assert impl.activate(state, "inv1") is True
        assert impl.activate(state, "inv1") is False
        assert spell.uses["charges"] == 2

    def test_activate_with_explicit_target(self, setup):
        state, bus, inv, inst, impl, mgr = setup
        first = _add_spell(state, inv, "inst_s1", charges=0)
        second = _add_spell(state, inv, "inst_s2", charges=1)
        assert impl.activate(state, "inv1", target_instance_id="inst_s2") is True
        assert first.uses["charges"] == 0
        assert second.uses["charges"] == 2
