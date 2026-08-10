"""Tests for Arcane Initiate (Level 3). (03271)

强制-入场后：放置1毁灭或2恐惧（简化默认2恐惧）；
【快速】横置：搜牌库顶3张找1张法术并抽取，然后洗牌。
"""

import pytest
from backend.cards.mystic.arcane_initiate_lv3 import ArcaneInitiateLv3
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, ScenarioState,
)
from backend.tests.conftest import (
    make_asset_data, make_event_data, make_investigator_data, make_skill_data,
)


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

    state.card_database["arcane_initiate_lv3"] = make_asset_data(
        id="arcane_initiate_lv3", name="Arcane Initiate", cost=0,
        traits=["ally", "sorcerer"], health=1, sanity=3,
    )
    state.card_database["shrivelling_lv0"] = make_asset_data(
        id="shrivelling_lv0", name="Shrivelling", traits=["spell"],
    )
    state.card_database["machete_lv0"] = make_asset_data(
        id="machete_lv0", name="Machete", traits=["item", "weapon"],
    )
    state.card_database["guts_lv0"] = make_skill_data(id="guts_lv0")

    inst = CardInstance(
        instance_id="inst_ai", card_id="arcane_initiate_lv3",
        owner_id="inv1", controller_id="inv1",
    )
    state.cards_in_play["inst_ai"] = inst
    inv.play_area.append("inst_ai")

    impl = ArcaneInitiateLv3("inst_ai")
    impl.register(bus, "inst_ai")
    return state, bus, inv, inst, impl


def _enter_play(bus, state, **extra):
    ctx = EventContext(
        game_state=state, event=GameEvent.CARD_ENTERS_PLAY,
        investigator_id="inv1", target="inst_ai", extra=extra,
    )
    bus.emit(ctx)
    return ctx


class TestArcaneInitiateLv3:
    def test_enters_play_places_2_horror_by_default(self, setup):
        """强制：默认放置2点恐惧（通常比毁灭更有利）。"""
        state, bus, inv, inst, impl = setup
        ctx = _enter_play(bus, state)
        assert inst.horror == 2
        assert inst.doom == 0
        assert ctx.extra["arcane_initiate_horror"] == 2

    def test_enters_play_can_place_doom_instead(self, setup):
        """选择分支：ctx.extra['choose_doom'] 时放置1毁灭。"""
        state, bus, inv, inst, impl = setup
        ctx = _enter_play(bus, state, choose_doom=True)
        assert inst.doom == 1
        assert inst.horror == 0
        assert ctx.extra["arcane_initiate_doom"] is True

    def test_search_spell_from_top_3(self, setup):
        """横置：牌库顶3张中抽取第一张法术卡。"""
        state, bus, inv, inst, impl = setup
        inv.deck = ["guts_lv0", "shrivelling_lv0", "machete_lv0", "guts_lv0"]
        assert impl.activate(state, "inv1") is True
        assert inst.exhausted is True
        assert "shrivelling_lv0" in inv.hand
        assert "shrivelling_lv0" not in inv.deck
        assert len(inv.deck) == 3

    def test_search_miss_still_shuffles(self, setup):
        """顶3张无法术：不抽牌，牌库被洗（张数不变）。"""
        state, bus, inv, inst, impl = setup
        inv.deck = ["guts_lv0", "machete_lv0", "guts_lv0"]
        assert impl.activate(state, "inv1") is True
        assert inv.hand == []
        assert len(inv.deck) == 3

    def test_search_only_looks_at_top_3(self, setup):
        """法术在第4张时不被抽到。"""
        state, bus, inv, inst, impl = setup
        inv.deck = ["guts_lv0", "machete_lv0", "guts_lv0", "shrivelling_lv0"]
        assert impl.activate(state, "inv1") is True
        assert "shrivelling_lv0" not in inv.hand

    def test_cannot_activate_while_exhausted(self, setup):
        state, bus, inv, inst, impl = setup
        inst.exhausted = True
        inv.deck = ["shrivelling_lv0"]
        assert impl.activate(state, "inv1") is False
