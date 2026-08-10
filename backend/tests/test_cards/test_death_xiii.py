"""Tests for Death • XIII (Level 1). (05027)

+1智力；游戏开始时在起始手牌中则放置入场（塔罗槽）。
"""

import importlib

import pytest

from backend.engine.event_bus import EventBus, EventContext

DeathXIII = importlib.import_module(
    "backend.cards.seeker.death_•_xiii_lv1").DeathXIII
from backend.engine.slots import SlotManager
from backend.models.enums import GameEvent, Phase, Skill, SlotType
from backend.models.state import GameState, InvestigatorState, ScenarioState
from backend.tests.conftest import make_asset_data, make_investigator_data

CARD_ID = "death_•_xiii_lv1"


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()
    state.slot_managers = {"inv1": SlotManager()}

    inv_data = make_investigator_data(intellect=3)
    state.card_database[inv_data.id] = inv_data
    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1",
    )
    state.investigators["inv1"] = inv
    state.card_database[CARD_ID] = make_asset_data(
        id=CARD_ID, name="Death • XIII", slots=[SlotType.TAROT],
        traits=["tarot"],
    )
    impl = DeathXIII("inst_temp")
    impl.register(bus, "inst_temp")
    return state, bus, inv, impl


class TestDeathXIII:
    def test_opening_hand_puts_into_play(self, setup):
        """SETUP 阶段抽到本卡：从手牌放置入场并占塔罗槽。"""
        state, bus, inv, impl = setup
        state.scenario.current_phase = Phase.SETUP
        inv.hand = [CARD_ID]
        ctx = EventContext(
            game_state=state, event=GameEvent.CARD_DRAWN,
            investigator_id="inv1", extra={"card_id": CARD_ID},
        )
        bus.emit(ctx)
        new_id = ctx.extra.get("death_xiii_into_play")
        assert new_id is not None
        assert CARD_ID not in inv.hand
        assert new_id in inv.play_area
        mgr = state.slot_managers["inv1"]
        assert mgr.available(SlotType.TAROT) == 0

    def test_drawn_outside_setup_stays_in_hand(self, setup):
        state, bus, inv, impl = setup
        state.scenario.current_phase = Phase.INVESTIGATION
        inv.hand = [CARD_ID]
        bus.emit(EventContext(
            game_state=state, event=GameEvent.CARD_DRAWN,
            investigator_id="inv1", extra={"card_id": CARD_ID},
        ))
        assert CARD_ID in inv.hand
        assert not inv.play_area

    def test_intellect_bonus_while_in_play(self, setup):
        state, bus, inv, impl = setup
        state.scenario.current_phase = Phase.SETUP
        inv.hand = [CARD_ID]
        bus.emit(EventContext(
            game_state=state, event=GameEvent.CARD_DRAWN,
            investigator_id="inv1", extra={"card_id": CARD_ID},
        ))
        ctx = EventContext(
            game_state=state, event=GameEvent.SKILL_VALUE_DETERMINED,
            investigator_id="inv1", skill_type=Skill.INTELLECT, amount=3,
        )
        bus.emit(ctx)
        assert ctx.amount == 4
        # 其它技能不加
        ctx2 = EventContext(
            game_state=state, event=GameEvent.SKILL_VALUE_DETERMINED,
            investigator_id="inv1", skill_type=Skill.COMBAT, amount=3,
        )
        bus.emit(ctx2)
        assert ctx2.amount == 3
