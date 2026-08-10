"""Tests for Rite of Seeking (Level 0 & 2). (02028 / 51007)

【行动】花1充能：调查，用意志代替智力；成功额外发现1线索；
坏标记 → 检定结束后失去所有剩余行动并立刻结束回合（lv2 同样保留该惩罚）。
lv2 另获 +2。
"""

import pytest
from backend.cards.mystic.rite_of_seeking_lv0 import RiteOfSeeking
from backend.cards.mystic.rite_of_seeking_lv2 import RiteOfSeekingLv2
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import ChaosTokenType, GameEvent, Skill
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, LocationState, ScenarioState,
)
from backend.tests.conftest import (
    make_asset_data, make_investigator_data, make_location_data,
)


@pytest.fixture(params=["rite_of_seeking_lv0", "rite_of_seeking_lv2"])
def setup(request):
    card_id = request.param
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()

    inv_data = make_investigator_data(willpower=5, intellect=3)
    state.card_database[inv_data.id] = inv_data
    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1",
    )
    state.investigators["inv1"] = inv

    loc_data = make_location_data(id="loc1", shroud=2)
    state.card_database[loc_data.id] = loc_data
    state.locations["loc1"] = LocationState(
        location_id="loc1", card_data=loc_data, clues=3,
    )

    state.card_database[card_id] = make_asset_data(
        id=card_id, name="Rite of Seeking", traits=["spell"],
        uses={"charges": 3},
    )
    inst = CardInstance(
        instance_id="inst_ros", card_id=card_id,
        owner_id="inv1", controller_id="inv1",
    )
    inst.uses = {"charges": 3}
    state.cards_in_play["inst_ros"] = inst
    inv.play_area.append("inst_ros")

    cls = RiteOfSeekingLv2 if card_id == "rite_of_seeking_lv2" else RiteOfSeeking
    impl = cls("inst_ros")
    impl.register(bus, "inst_ros")
    return state, bus, inv, inst, impl, card_id


class TestRiteOfSeekingCommon:
    def test_activate_spends_charge_without_exhaust(self, setup):
        """官方卡面无横置要求。"""
        state, bus, inv, inst, impl, card_id = setup
        assert impl.activate(state, "inv1") is True
        assert inst.uses["charges"] == 2
        assert inst.exhausted is False

    def test_willpower_substitutes_intellect(self, setup):
        state, bus, inv, inst, impl, card_id = setup
        impl.activate(state, "inv1")
        ctx = EventContext(
            game_state=state, event=GameEvent.SKILL_VALUE_DETERMINED,
            investigator_id="inv1", skill_type=Skill.INTELLECT, amount=3,
        )
        bus.emit(ctx)
        expected = 5 + (2 if card_id == "rite_of_seeking_lv2" else 0)
        assert ctx.amount == expected

    def test_extra_clue_on_success(self, setup):
        """成功：额外发现1线索（正常1+额外1=2）。"""
        state, bus, inv, inst, impl, card_id = setup
        impl.activate(state, "inv1")
        loc = state.locations["loc1"]
        # 模拟调查成功发现1线索后触发 CLUE_DISCOVERED
        loc.clues -= 1
        inv.clues += 1
        bus.emit(EventContext(
            game_state=state, event=GameEvent.CLUE_DISCOVERED,
            investigator_id="inv1", location_id="loc1", amount=1,
        ))
        assert inv.clues == 2
        assert loc.clues == 1

    def test_bad_token_ends_turn(self, setup):
        """坏标记：检定结束后失去所有剩余行动并结束回合（lv2 同样适用）。"""
        state, bus, inv, inst, impl, card_id = setup
        inv.actions_remaining = 2
        impl.activate(state, "inv1")
        bus.emit(EventContext(
            game_state=state, event=GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="inv1", chaos_token=ChaosTokenType.CULTIST,
        ))
        ctx = EventContext(
            game_state=state, event=GameEvent.SKILL_TEST_ENDS,
            investigator_id="inv1",
        )
        bus.emit(ctx)
        assert inv.actions_remaining == 0
        assert ctx.extra[f"{card_id}_turn_ended"] is True

    def test_good_token_keeps_actions(self, setup):
        state, bus, inv, inst, impl, card_id = setup
        inv.actions_remaining = 2
        impl.activate(state, "inv1")
        bus.emit(EventContext(
            game_state=state, event=GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="inv1", chaos_token=ChaosTokenType.ZERO,
        ))
        bus.emit(EventContext(
            game_state=state, event=GameEvent.SKILL_TEST_ENDS,
            investigator_id="inv1",
        ))
        assert inv.actions_remaining == 2
