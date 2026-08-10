"""Tests for Encyclopedia (Level 2)."""

import pytest
from backend.cards.seeker.encyclopedia_lv2 import Encyclopedia
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent, Skill
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, LocationState, ScenarioState,
)
from backend.tests.conftest import (
    make_asset_data, make_investigator_data, make_location_data,
)


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()

    enc_data = make_asset_data(
        id="encyclopedia_lv2", name="Encyclopedia",
        traits=["item", "tome"],
    )
    state.card_database["encyclopedia_lv2"] = enc_data

    inv_data = make_investigator_data(intellect=3)
    state.card_database[inv_data.id] = inv_data
    loc_data = make_location_data()
    state.card_database[loc_data.id] = loc_data

    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="test_location",
    )
    state.investigators["inv1"] = inv
    state.locations["test_location"] = LocationState(
        location_id="test_location", card_data=loc_data, clues=0,
    )

    impl = Encyclopedia("inst_enc")
    impl.register(bus, "inst_enc")

    ci = CardInstance(
        instance_id="inst_enc", card_id="encyclopedia_lv2",
        owner_id="inv1", controller_id="inv1",
    )
    state.cards_in_play["inst_enc"] = ci
    inv.play_area.append("inst_enc")

    return state, bus, inv, impl


def _skill_value_ctx(state, skill, amount=3):
    ctx = EventContext(
        game_state=state, event=GameEvent.SKILL_VALUE_DETERMINED,
        investigator_id="inv1", skill_type=skill, amount=amount,
    )
    return ctx


class TestEncyclopedia:
    def test_card_data_has_tome_trait(self, setup):
        """Encyclopedia has the 'tome' trait."""
        state, bus, inv, impl = setup
        card_data = state.card_database["encyclopedia_lv2"]
        assert "tome" in card_data.traits

    def test_activate_exhausts_and_boosts_chosen_skill(self, setup):
        """消耗启动：所选技能+2（默认智力）直到阶段结束。"""
        state, bus, inv, impl = setup

        ok = impl.activate(state, "inv1", skill=Skill.AGILITY)

        assert ok is True
        assert state.get_card_instance("inst_enc").exhausted is True

        agi = _skill_value_ctx(state, Skill.AGILITY, amount=2)
        bus.emit(agi)
        assert agi.amount == 4  # +2

        # 其他技能不加值
        intl = _skill_value_ctx(state, Skill.INTELLECT, amount=3)
        bus.emit(intl)
        assert intl.amount == 3

    def test_activate_default_skill_intellect(self, setup):
        """会话层通用通道不传参时默认智力。"""
        state, bus, inv, impl = setup
        assert impl.activate(state, "inv1") is True

        intl = _skill_value_ctx(state, Skill.INTELLECT, amount=3)
        bus.emit(intl)
        assert intl.amount == 5

    def test_buff_expires_at_phase_end(self, setup):
        """阶段结束时移除加值。"""
        state, bus, inv, impl = setup
        impl.activate(state, "inv1", skill=Skill.AGILITY)

        bus.emit(EventContext(
            game_state=state, event=GameEvent.INVESTIGATION_PHASE_ENDS,
            investigator_id="inv1",
        ))

        agi = _skill_value_ctx(state, Skill.AGILITY, amount=2)
        bus.emit(agi)
        assert agi.amount == 2  # 已过期

    def test_activate_fails_when_exhausted(self, setup):
        state, bus, inv, impl = setup
        state.get_card_instance("inst_enc").exhausted = True
        assert impl.activate(state, "inv1") is False
