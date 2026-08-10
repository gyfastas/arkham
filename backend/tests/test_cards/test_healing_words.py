"""Tests for Healing Words (Level 0 / Level 3) and Meditative Trance (Level 0)."""

import pytest
from backend.cards.mystic.healing_words_lv0 import HealingWords
from backend.cards.mystic.healing_words_lv3 import HealingWordsLv3
from backend.cards.mystic.meditative_trance_lv0 import MeditativeTrance
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent, SlotType
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, LocationState, ScenarioState,
)
from backend.tests.conftest import make_asset_data, make_investigator_data, make_location_data


def _state_with_inv():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    inv_data = make_investigator_data()
    state.card_database[inv_data.id] = inv_data
    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1")
    state.investigators["inv1"] = inv
    ld = make_location_data(id="loc1")
    state.card_database["loc1"] = ld
    state.locations["loc1"] = LocationState(location_id="loc1", card_data=ld)
    return state, inv


def _add_asset(state, inv, card_id, instance_id, uses=None, slots=None):
    state.card_database[card_id] = make_asset_data(
        id=card_id, name=card_id, traits=["spell"], uses=uses,
        slots=slots or [SlotType.ARCANE])
    inst = CardInstance(
        instance_id=instance_id, card_id=card_id,
        owner_id="inv1", controller_id="inv1")
    if uses:
        inst.uses = dict(uses)
    state.cards_in_play[instance_id] = inst
    inv.play_area.append(instance_id)
    return inst


class TestHealingWords:
    def test_lv0_heals_1_damage(self):
        state, inv = _state_with_inv()
        inv.damage = 2
        inst = _add_asset(state, inv, "healing_words_lv0", "inst_hw",
                          uses={"charges": 3})
        impl = HealingWords("inst_hw")
        assert impl.activate(state, "inv1") is True
        assert inv.damage == 1
        assert inst.uses["charges"] == 2

    def test_lv0_rejects_other_location(self):
        state, inv = _state_with_inv()
        other_data = make_investigator_data(id="other", name="Other")
        state.card_database["other"] = other_data
        other = InvestigatorState(
            investigator_id="inv2", card_data=other_data, location_id="elsewhere")
        other.damage = 1
        state.investigators["inv2"] = other
        _add_asset(state, inv, "healing_words_lv0", "inst_hw",
                   uses={"charges": 3})
        impl = HealingWords("inst_hw")
        assert impl.activate(state, "inv1", ["inv2"]) is False

    def test_lv3_heals_2_split(self):
        state, inv = _state_with_inv()
        inv.damage = 1
        other_data = make_investigator_data(id="other", name="Other")
        state.card_database["other"] = other_data
        other = InvestigatorState(
            investigator_id="inv2", card_data=other_data, location_id="loc1")
        other.damage = 1
        state.investigators["inv2"] = other
        inst = _add_asset(state, inv, "healing_words_lv3", "inst_hw3",
                          uses={"charges": 4})
        impl = HealingWordsLv3("inst_hw3")
        assert impl.activate(state, "inv1", ["inv1", "inv2"]) is True
        assert inv.damage == 0 and other.damage == 0
        assert inst.uses["charges"] == 3

    def test_lv3_default_heals_self_2(self):
        state, inv = _state_with_inv()
        inv.damage = 2
        _add_asset(state, inv, "healing_words_lv3", "inst_hw3",
                   uses={"charges": 4})
        impl = HealingWordsLv3("inst_hw3")
        assert impl.activate(state, "inv1") is True
        assert inv.damage == 0


class TestMeditativeTrance:
    def test_heal_per_filled_arcane_slot(self):
        state, inv = _state_with_inv()
        inv.damage = 1
        inv.horror = 1
        _add_asset(state, inv, "shrivelling_lv0", "inst_s1")
        _add_asset(state, inv, "scrying_lv0", "inst_s2")
        bus = EventBus()
        impl = MeditativeTrance("temp")
        impl.register(bus, "temp")
        ctx = EventContext(
            game_state=state, event=GameEvent.CARD_PLAYED,
            investigator_id="inv1", extra={"card_id": "meditative_trance_lv0"})
        bus.emit(ctx)
        # 2个已占奥秘槽：默认先治愈1伤害，再治愈1恐惧
        assert inv.damage == 0
        assert inv.horror == 0
        assert ctx.extra["meditative_trance_healed_damage"] == 1
        assert ctx.extra["meditative_trance_healed_horror"] == 1

    def test_no_arcane_slots_no_heal(self):
        state, inv = _state_with_inv()
        inv.damage = 1
        bus = EventBus()
        impl = MeditativeTrance("temp")
        impl.register(bus, "temp")
        bus.emit(EventContext(
            game_state=state, event=GameEvent.CARD_PLAYED,
            investigator_id="inv1", extra={"card_id": "meditative_trance_lv0"}))
        assert inv.damage == 1
