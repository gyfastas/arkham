"""Tests for Occult Lexicon (Level 0)."""

import pytest
from backend.cards.seeker.occult_lexicon_lv0 import OccultLexicon
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent, PlayerClass
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

    inv_data = make_investigator_data()
    state.card_database[inv_data.id] = inv_data
    loc_data = make_location_data()
    state.card_database[loc_data.id] = loc_data
    state.card_database["blood_rite_lv0"] = make_asset_data(
        id="blood_rite_lv0", cost=0, card_class=PlayerClass.SEEKER)

    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data,
        location_id="test_location", deck=["rest_1"],
    )
    state.investigators["inv1"] = inv
    state.locations["test_location"] = LocationState(
        location_id="test_location", card_data=loc_data,
    )

    inst = CardInstance(
        instance_id="ol_1", card_id="occult_lexicon_lv0",
        owner_id="inv1", controller_id="inv1",
    )
    state.cards_in_play["ol_1"] = inst
    inv.play_area.append("ol_1")

    impl = OccultLexicon("ol_1")
    impl.register(bus, "ol_1")
    return state, bus, inv, impl


def _enters_play(state, bus):
    ctx = EventContext(
        game_state=state, event=GameEvent.CARD_ENTERS_PLAY,
        investigator_id="inv1", target="ol_1",
        extra={"card_id": "occult_lexicon_lv0"},
    )
    bus.emit(ctx)
    return ctx


class TestOccultLexicon:
    def test_enters_play_fetches_blood_rites(self, setup):
        """入场：1张鲜血仪式入手，2张混洗入牌堆。"""
        state, bus, inv, impl = setup
        ctx = _enters_play(state, bus)
        assert ctx.extra["occult_lexicon_fetched"] == 3
        assert inv.hand.count("blood_rite_lv0") == 1
        assert inv.deck.count("blood_rite_lv0") == 2
        assert len(inv.deck) == 3  # 2鲜血仪式 + 原有1张

    def test_leaves_play_sets_blood_rites_aside(self, setup):
        """离场：所有鲜血仪式（手牌/牌堆/弃牌堆）放回绑定池。"""
        state, bus, inv, impl = setup
        _enters_play(state, bus)
        # 模拟其中1张被用掉入弃牌堆
        inv.hand.remove("blood_rite_lv0")
        inv.discard.append("blood_rite_lv0")

        ctx = EventContext(
            game_state=state, event=GameEvent.CARD_LEAVES_PLAY,
            investigator_id="inv1", target="ol_1",
            extra={"card_id": "occult_lexicon_lv0"},
        )
        bus.emit(ctx)
        assert ctx.extra["occult_lexicon_set_aside"] == 3
        assert "blood_rite_lv0" not in inv.hand
        assert "blood_rite_lv0" not in inv.deck
        assert "blood_rite_lv0" not in inv.discard
        assert state.scenario.vars["bonded_cards"].count("blood_rite_lv0") == 3

    def test_bonded_pool_reused(self, setup):
        """绑定池已有副本时优先取用（不凭空增殖）。"""
        state, bus, inv, impl = setup
        state.scenario.vars["bonded_cards"] = ["blood_rite_lv0"] * 3
        _enters_play(state, bus)
        assert state.scenario.vars["bonded_cards"] == []
        assert inv.hand.count("blood_rite_lv0") == 1
