"""Tests for Jeremiah Kirby (Level 0)."""

import pytest
from backend.cards.seeker.jeremiah_kirby_lv0 import JeremiahKirby
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent, PlayerClass, Skill
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

    inv_data = make_investigator_data(intellect=3)
    state.card_database[inv_data.id] = inv_data
    loc_data = make_location_data()
    state.card_database[loc_data.id] = loc_data
    # 牌堆顶5张：费用 1,2,3,4,None（无费用不抽）
    for cid, cost in [("c1", 1), ("c2", 2), ("c3", 3), ("c4", 4), ("cx", None)]:
        state.card_database[cid] = make_asset_data(
            id=cid, cost=cost, card_class=PlayerClass.SEEKER)
    state.card_database["jeremiah_kirby_lv0"] = make_asset_data(
        id="jeremiah_kirby_lv0", cost=4, card_class=PlayerClass.SEEKER)

    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data,
        location_id="test_location",
        deck=["c1", "c2", "c3", "c4", "cx", "rest"],
    )
    state.investigators["inv1"] = inv
    state.locations["test_location"] = LocationState(
        location_id="test_location", card_data=loc_data,
    )

    inst = CardInstance(
        instance_id="jk_1", card_id="jeremiah_kirby_lv0",
        owner_id="inv1", controller_id="inv1",
    )
    state.cards_in_play["jk_1"] = inst
    inv.play_area.append("jk_1")

    impl = JeremiahKirby("jk_1")
    impl.register(bus, "jk_1")
    return state, bus, inv, impl


def _enters_play(state, bus, **extra):
    ctx = EventContext(
        game_state=state, event=GameEvent.CARD_ENTERS_PLAY,
        investigator_id="inv1", target="jk_1",
        extra={"card_id": "jeremiah_kirby_lv0", **extra},
    )
    bus.emit(ctx)
    return ctx


class TestJeremiahKirby:
    def test_intellect_bonus(self, setup):
        """常驻 +1 智力。"""
        state, bus, inv, impl = setup
        ctx = EventContext(
            game_state=state, event=GameEvent.SKILL_VALUE_DETERMINED,
            investigator_id="inv1", skill_type=Skill.INTELLECT, amount=3,
        )
        bus.emit(ctx)
        assert ctx.amount == 4

    def test_enters_play_even_draws_even_costs(self, setup):
        """入场反应：选偶数 → 抽取费用2和4的卡，无费用卡不抽。"""
        state, bus, inv, impl = setup
        _enters_play(state, bus, parity="even")
        assert "c2" in inv.hand
        assert "c4" in inv.hand
        assert "c1" not in inv.hand
        assert "cx" not in inv.hand
        # 其余混洗回牌堆（c1,c3,cx,rest 共4张）
        assert len(inv.deck) == 4

    def test_auto_parity_picks_more_draws(self, setup):
        """自动选择：偶数侧可抽2张 > 奇数侧1张 → 自动选偶数。"""
        state, bus, inv, impl = setup
        _enters_play(state, bus)
        assert "c2" in inv.hand and "c4" in inv.hand
        assert "c1" not in inv.hand

    def test_odd_parity(self, setup):
        """选奇数：只抽费用1和3的卡。"""
        state, bus, inv, impl = setup
        _enters_play(state, bus, parity="odd")
        assert "c1" in inv.hand and "c3" in inv.hand
        assert "c2" not in inv.hand
