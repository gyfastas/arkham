"""Tests for Read the Signs (Level 0) and Scroll of Prophecies / Scroll of Secrets."""

import pytest
from backend.cards.mystic.read_the_signs_lv0 import ReadTheSigns
from backend.cards.mystic.scroll_of_prophecies_lv0 import ScrollOfProphecies
from backend.cards.mystic.scroll_of_secrets_lv3 import ScrollOfSecretsLv3
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent, Skill
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, LocationState, ScenarioState,
)
from backend.tests.conftest import make_asset_data, make_investigator_data, make_location_data


def _state():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()
    inv_data = make_investigator_data(willpower=4, intellect=3)
    state.card_database[inv_data.id] = inv_data
    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1",
        deck=["d1", "d2", "d3", "d4", "d5"])
    state.investigators["inv1"] = inv
    ld = make_location_data(id="loc1")
    state.card_database["loc1"] = ld
    state.locations["loc1"] = LocationState(
        location_id="loc1", card_data=ld, clues=2)
    return state, bus, inv


class TestReadTheSigns:
    def test_adds_willpower_and_extra_clue(self):
        state, bus, inv = _state()
        impl = ReadTheSigns("temp")
        impl.register(bus, "temp")
        bus.emit(EventContext(
            game_state=state, event=GameEvent.CARD_PLAYED,
            investigator_id="inv1", extra={"card_id": "read_the_signs_lv0"}))

        ctx = EventContext(
            game_state=state, event=GameEvent.SKILL_VALUE_DETERMINED,
            investigator_id="inv1", skill_type=Skill.INTELLECT, amount=3)
        bus.emit(ctx)
        assert ctx.amount == 7  # 智力3 + 意志4

        clue_ctx = EventContext(
            game_state=state, event=GameEvent.CLUE_DISCOVERED,
            investigator_id="inv1", location_id="loc1", amount=1)
        bus.emit(clue_ctx)
        assert state.locations["loc1"].clues == 1
        assert inv.clues == 1

        # 检定结束后效果清除
        bus.emit(EventContext(
            game_state=state, event=GameEvent.SKILL_TEST_ENDS,
            investigator_id="inv1"))
        ctx2 = EventContext(
            game_state=state, event=GameEvent.SKILL_VALUE_DETERMINED,
            investigator_id="inv1", skill_type=Skill.INTELLECT, amount=3)
        bus.emit(ctx2)
        assert ctx2.amount == 3


class TestScrollOfProphecies:
    def test_draw3_discard1(self):
        state, bus, inv = _state()
        state.card_database["scroll_of_prophecies_lv0"] = make_asset_data(
            id="scroll_of_prophecies_lv0", name="Scroll of Prophecies",
            traits=["item", "tome"], uses={"secrets": 4})
        inst = CardInstance(
            instance_id="inst_sop", card_id="scroll_of_prophecies_lv0",
            owner_id="inv1", controller_id="inv1")
        inst.uses = {"secrets": 4}
        state.cards_in_play["inst_sop"] = inst
        inv.play_area.append("inst_sop")

        impl = ScrollOfProphecies("inst_sop")
        assert impl.activate(state, "inv1") is True
        assert inst.uses["secrets"] == 3
        assert inv.hand == ["d1", "d2"]  # 抽3张后默认弃最后1张(d3)
        assert inv.discard == ["d3"]
        assert inv.deck == ["d4", "d5"]

    def test_discard_specific_card(self):
        state, bus, inv = _state()
        state.card_database["scroll_of_prophecies_lv0"] = make_asset_data(
            id="scroll_of_prophecies_lv0", name="Scroll", uses={"secrets": 4})
        inst = CardInstance(
            instance_id="inst_sop", card_id="scroll_of_prophecies_lv0",
            owner_id="inv1", controller_id="inv1")
        inst.uses = {"secrets": 4}
        state.cards_in_play["inst_sop"] = inst
        inv.play_area.append("inst_sop")
        impl = ScrollOfProphecies("inst_sop")
        assert impl.activate(state, "inv1", discard_card_id="d1") is True
        assert inv.discard == ["d1"]
        assert inv.hand == ["d2", "d3"]


class TestScrollOfSecretsLv3:
    def _make(self, state, inv):
        state.card_database["scroll_of_secrets_lv3"] = make_asset_data(
            id="scroll_of_secrets_lv3", name="Scroll of Secrets",
            traits=["item", "tome"], uses={"secrets": 4})
        inst = CardInstance(
            instance_id="inst_sos", card_id="scroll_of_secrets_lv3",
            owner_id="inv1", controller_id="inv1")
        inst.uses = {"secrets": 4}
        state.cards_in_play["inst_sos"] = inst
        inv.play_area.append("inst_sos")
        return inst, ScrollOfSecretsLv3("inst_sos")

    def test_peek_top_default_keeps(self):
        state, bus, inv = _state()
        inst, impl = self._make(state, inv)
        seen = impl.activate(state, "inv1")
        assert seen == "d1"
        assert inv.deck == ["d1", "d2", "d3", "d4", "d5"]
        assert inst.exhausted is True
        assert inst.uses["secrets"] == 3

    def test_discard_mode(self):
        state, bus, inv = _state()
        inst, impl = self._make(state, inv)
        seen = impl.activate(state, "inv1", mode="discard")
        assert seen == "d1"
        assert inv.deck == ["d2", "d3", "d4", "d5"]
        assert inv.discard == ["d1"]

    def test_bottom_mode(self):
        state, bus, inv = _state()
        inst, impl = self._make(state, inv)
        impl.activate(state, "inv1", mode="bottom")
        assert inv.deck == ["d2", "d3", "d4", "d5", "d1"]

    def test_hand_mode(self):
        state, bus, inv = _state()
        inst, impl = self._make(state, inv)
        impl.activate(state, "inv1", mode="hand")
        assert inv.hand == ["d1"]
        assert inv.deck == ["d2", "d3", "d4", "d5"]

    def test_encounter_deck_bottom_card(self):
        state, bus, inv = _state()
        inst, impl = self._make(state, inv)
        state.scenario.encounter_deck = ["e1", "e2", "e3"]
        seen = impl.activate(state, "inv1", target_encounter_deck=True,
                             from_bottom=True, mode="discard")
        assert seen == "e3"
        assert state.scenario.encounter_deck == ["e1", "e2"]
        assert state.scenario.encounter_discard == ["e3"]
