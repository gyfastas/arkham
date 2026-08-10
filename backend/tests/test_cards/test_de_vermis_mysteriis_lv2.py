"""Tests for De Vermis Mysteriis (Level 2). (05235)

[action]消耗+1毁灭：从弃牌堆打出法术/洞察事件（费用-1），结算后移出游戏。
"""

import pytest
from backend.cards.mystic.de_vermis_mysteriis_lv2 import DeVermisMysteriis
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, ScenarioState,
)
from backend.tests.conftest import (
    make_asset_data, make_event_data, make_investigator_data,
)


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()
    inv_data = make_investigator_data()
    state.card_database[inv_data.id] = inv_data
    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1",
        resources=5,
    )
    state.investigators["inv1"] = inv
    state.card_database["de_vermis_mysteriis_lv2"] = make_asset_data(
        id="de_vermis_mysteriis_lv2", name="De Vermis Mysteriis",
        traits=["item", "tome"])
    spell = make_event_data(id="spell_event", name="Spell", cost=3)
    spell.traits = ["spell"]
    state.card_database["spell_event"] = spell
    insight = make_event_data(id="insight_event", name="Insight", cost=1)
    insight.traits = ["insight"]
    state.card_database["insight_event"] = insight
    tactic = make_event_data(id="tactic_event", name="Tactic", cost=1)
    tactic.traits = ["tactic"]
    state.card_database["tactic_event"] = tactic

    inst = CardInstance(
        instance_id="inst_dvm", card_id="de_vermis_mysteriis_lv2",
        owner_id="inv1", controller_id="inv1",
    )
    state.cards_in_play["inst_dvm"] = inst
    inv.play_area.append("inst_dvm")
    impl = DeVermisMysteriis("inst_dvm")
    impl.register(bus, "inst_dvm")
    return state, bus, inv, inst, impl


class TestDeVermisMysteriis:
    def test_replay_spell_from_discard_reduced_cost(self, setup):
        """弃牌堆的法术事件：费用3→2，消耗+1毁灭，结算后移出游戏。"""
        state, bus, inv, inst, impl = setup
        inv.discard = ["spell_event"]
        played = impl.activate(state, "inv1")
        assert played == "spell_event"
        assert inst.exhausted is True
        assert inst.doom == 1
        assert inv.resources == 3  # 5 - (3-1)
        assert inv.discard == []
        assert "spell_event" in state.scenario.vars["removed_from_game"]

    def test_emits_card_played(self, setup):
        """补发 CARD_PLAYED（监听类效果可响应）。"""
        state, bus, inv, inst, impl = setup
        seen = []
        bus.register(
            GameEvent.CARD_PLAYED,
            lambda ctx: seen.append(ctx.extra.get("card_id")),
        )
        inv.discard = ["insight_event"]
        impl.activate(state, "inv1")
        assert seen == ["insight_event"]

    def test_auto_target_skips_non_spell_insight(self, setup):
        """自动目标：跳过非法术/洞察事件。"""
        state, bus, inv, inst, impl = setup
        inv.discard = ["tactic_event", "insight_event"]
        played = impl.activate(state, "inv1")
        assert played == "insight_event"
        assert inv.resources == 5  # 费用1-1=0

    def test_no_valid_target_returns_none(self, setup):
        state, bus, inv, inst, impl = setup
        inv.discard = ["tactic_event"]
        assert impl.activate(state, "inv1") is None
        assert inst.exhausted is False
        assert inst.doom == 0

    def test_exhausted_blocks_activate(self, setup):
        state, bus, inv, inst, impl = setup
        inst.exhausted = True
        inv.discard = ["spell_event"]
        assert impl.activate(state, "inv1") is None

    def test_insufficient_resources(self, setup):
        state, bus, inv, inst, impl = setup
        inv.resources = 1  # 减后费用2，不够
        inv.discard = ["spell_event"]
        assert impl.activate(state, "inv1") is None
        assert inv.discard == ["spell_event"]
