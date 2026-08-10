"""Tests for St. Hubert's Key (Level 0). (03269)

+1意志/+1智力/-2神智；因恐惧将被击败时丢弃本卡：立即治愈2恐惧。
"""

import pytest
from backend.cards.mystic.st_huberts_key_lv0 import StHubertsKey
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent, Skill
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, ScenarioState,
)
from backend.tests.conftest import make_asset_data, make_investigator_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()

    inv_data = make_investigator_data(willpower=3, intellect=2, sanity=7)
    state.card_database[inv_data.id] = inv_data
    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1",
    )
    state.investigators["inv1"] = inv

    state.card_database["st_huberts_key_lv0"] = make_asset_data(
        id="st_huberts_key_lv0", name="St. Hubert's Key", cost=4,
        traits=["item", "charm"], sanity=None,
    )
    inst = CardInstance(
        instance_id="inst_key", card_id="st_huberts_key_lv0",
        owner_id="inv1", controller_id="inv1",
    )
    state.cards_in_play["inst_key"] = inst
    inv.play_area.append("inst_key")

    impl = StHubertsKey("inst_key")
    impl.register(bus, "inst_key")
    return state, bus, inv, inst, impl


def _skill_ctx(state, skill, amount):
    return EventContext(
        game_state=state, event=GameEvent.SKILL_VALUE_DETERMINED,
        investigator_id="inv1", skill_type=skill, amount=amount,
    )


class TestStHubertsKeyPassive:
    def test_willpower_and_intellect_bonus(self, setup):
        state, bus, inv, inst, impl = setup
        ctx = _skill_ctx(state, Skill.WILLPOWER, 3)
        bus.emit(ctx)
        assert ctx.amount == 4
        ctx2 = _skill_ctx(state, Skill.INTELLECT, 2)
        bus.emit(ctx2)
        assert ctx2.amount == 3

    def test_no_bonus_to_other_skills(self, setup):
        state, bus, inv, inst, impl = setup
        ctx = _skill_ctx(state, Skill.COMBAT, 3)
        bus.emit(ctx)
        assert ctx.amount == 3

    def test_sanity_penalty_on_enter_and_leave(self, setup):
        """入场-2神智，离场恢复。"""
        state, bus, inv, inst, impl = setup
        base = inv.sanity
        bus.emit(EventContext(
            game_state=state, event=GameEvent.CARD_ENTERS_PLAY,
            investigator_id="inv1", target="inst_key",
        ))
        assert inv.sanity == base - 2
        bus.emit(EventContext(
            game_state=state, event=GameEvent.CARD_LEAVES_PLAY,
            investigator_id="inv1", target="inst_key",
        ))
        assert inv.sanity == base


class TestStHubertsKeySave:
    def test_save_from_horror_defeat(self, setup):
        """恐惧达标将被击败：丢弃本卡并治愈2恐惧，不再被击败。"""
        state, bus, inv, inst, impl = setup
        # 入场-2神智：神智 7-2=5；恐惧5 → 达到上限
        inv.sanity_bonus = -2
        inv.horror = 5
        assert inv.is_defeated
        ctx = EventContext(
            game_state=state, event=GameEvent.INVESTIGATOR_DEFEATED,
            investigator_id="inv1",
        )
        bus.emit(ctx)
        assert ctx.extra["st_huberts_key_saved"] is True
        assert "inst_key" not in inv.play_area
        assert "st_huberts_key_lv0" in inv.discard
        assert inv.horror == 3
        assert inv.sanity == 7  # -2神智移除
        assert not inv.is_defeated

    def test_no_save_from_damage_defeat(self, setup):
        """仅伤害达标（恐惧未达标）时不触发。"""
        state, bus, inv, inst, impl = setup
        inv.sanity_bonus = -2
        inv.damage = 7  # 健康7 → 伤害击败
        inv.horror = 2
        assert inv.is_defeated
        ctx = EventContext(
            game_state=state, event=GameEvent.INVESTIGATOR_DEFEATED,
            investigator_id="inv1",
        )
        bus.emit(ctx)
        assert "st_huberts_key_saved" not in ctx.extra
        assert "inst_key" in inv.play_area

    def test_no_save_when_not_in_play(self, setup):
        state, bus, inv, inst, impl = setup
        inv.play_area.remove("inst_key")
        inv.horror = 7
        ctx = EventContext(
            game_state=state, event=GameEvent.INVESTIGATOR_DEFEATED,
            investigator_id="inv1",
        )
        bus.emit(ctx)
        assert "st_huberts_key_saved" not in ctx.extra
        assert inv.horror == 7
