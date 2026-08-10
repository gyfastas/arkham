"""Tests for Ancestral Knowledge (Level 3). (07303)

开局附着5张随机非弱点技能牌；[快速]横置抽取1张附着技能牌。
"""

import pytest

from backend.cards.seeker.ancestral_knowledge_lv3 import (
    VAR, AncestralKnowledge,
)
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, ScenarioState,
)
from backend.tests.conftest import (
    make_asset_data, make_investigator_data, make_skill_data,
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
    skills = [f"skill_{i}" for i in range(7)]
    for cid in skills:
        state.card_database[cid] = make_skill_data(id=cid, name=cid)
    state.card_database["asset_x"] = make_asset_data(id="asset_x")
    inv.deck = skills + ["asset_x", "asset_x"]
    state.investigators["inv1"] = inv

    state.card_database["ancestral_knowledge_lv3"] = make_asset_data(
        id="ancestral_knowledge_lv3", name="Ancestral Knowledge",
        traits=["talent"],
    )
    inst = CardInstance(
        instance_id="inst_ak", card_id="ancestral_knowledge_lv3",
        owner_id="inv1", controller_id="inv1",
    )
    state.cards_in_play["inst_ak"] = inst
    inv.play_area.append("inst_ak")

    impl = AncestralKnowledge("inst_ak")
    impl.register(bus, "inst_ak")
    return state, bus, inv, inst, impl


class TestSetupOpening:
    def test_attaches_5_random_skills(self, setup):
        """开局：5张非弱点技能牌从牌堆附着到本卡。"""
        state, bus, inv, inst, impl = setup
        found = impl.setup_opening(state, "inv1")
        assert len(found) == 5
        assert len(inv.deck) == 9 - 5  # 7技能+2资产 → 抽走5技能
        assert all(cid.startswith("skill_") for cid in found)
        assert impl.attached_skills(state, "inv1") == found
        # 资产不被附着
        assert "asset_x" in inv.deck

    def test_idempotent(self, setup):
        state, bus, inv, inst, impl = setup
        first = impl.setup_opening(state, "inv1")
        assert impl.setup_opening(state, "inv1") == []
        assert impl.attached_skills(state, "inv1") == first

    def test_enters_play_triggers_setup(self, setup):
        state, bus, inv, inst, impl = setup
        bus.emit(EventContext(
            game_state=state, event=GameEvent.CARD_ENTERS_PLAY,
            investigator_id="inv1", target="inst_ak",
        ))
        assert len(impl.attached_skills(state, "inv1")) == 5


class TestDrawAttached:
    def test_activate_draws_attached_skill(self, setup):
        """[快速]横置：抽取1张附着的技能牌。"""
        state, bus, inv, inst, impl = setup
        found = impl.setup_opening(state, "inv1")
        expected = found[0]  # activate 会从附着列表移除该牌（共享列表，先取副本）
        assert impl.activate(state, "inv1") is True
        assert inst.exhausted is True
        assert expected in inv.hand
        assert len(impl.attached_skills(state, "inv1")) == 4

    def test_activate_empty_or_exhausted_fails(self, setup):
        state, bus, inv, inst, impl = setup
        assert impl.activate(state, "inv1") is False  # 未附着
        impl.setup_opening(state, "inv1")
        inst.exhausted = True
        assert impl.activate(state, "inv1") is False
