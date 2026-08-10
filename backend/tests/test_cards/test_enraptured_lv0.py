"""Tests for Enraptured (Level 0). (04157)

投入本卡的调查检定成功：在你控制的1张支援卡上放置1充能或1秘密
（简化：调查中=智力检定且无来源卡；目标取第一张带充能/秘密的支援）。
"""

import pytest
from backend.cards.mystic.enraptured_lv0 import Enraptured
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent, Skill
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
    state.investigators["inv1"] = inv
    state.card_database["enraptured_lv0"] = make_skill_data(
        id="enraptured_lv0", name="Enraptured",
        skill_icons={"intellect": 1})
    state.card_database["charge_asset"] = make_asset_data(
        id="charge_asset", name="C", uses={"charges": 1})
    state.card_database["secret_asset"] = make_asset_data(
        id="secret_asset", name="S", uses={"secrets": 1})
    impl = Enraptured("impl_enr")
    impl.register(bus, "impl_enr")
    return state, bus, inv, impl


def _add_asset(state, inv, iid, cid, uses):
    inst = CardInstance(
        instance_id=iid, card_id=cid, owner_id="inv1", controller_id="inv1")
    inst.uses = dict(uses)
    state.cards_in_play[iid] = inst
    inv.play_area.append(iid)
    return inst


def _success_ctx(state, skill=Skill.INTELLECT, source=None):
    return EventContext(
        game_state=state, event=GameEvent.SKILL_TEST_SUCCESSFUL,
        investigator_id="inv1", skill_type=skill, success=True,
        committed_cards=["enraptured_lv0"], source=source,
    )


class TestEnraptured:
    def test_places_charge_on_investigate_success(self, setup):
        """调查成功：支援+1充能。"""
        state, bus, inv, impl = setup
        asset = _add_asset(state, inv, "inst_c", "charge_asset", {"charges": 1})
        ctx = _success_ctx(state)
        bus.emit(ctx)
        assert asset.uses["charges"] == 2
        assert ctx.extra["enraptured_placed"]["kind"] == "charges"

    def test_places_secret_on_secret_asset(self, setup):
        state, bus, inv, impl = setup
        asset = _add_asset(state, inv, "inst_s", "secret_asset", {"secrets": 1})
        ctx = _success_ctx(state)
        bus.emit(ctx)
        assert asset.uses["secrets"] == 2
        assert ctx.extra["enraptured_placed"]["kind"] == "secrets"

    def test_no_placement_on_fight(self, setup):
        """战斗检定（有武器来源）不触发。"""
        state, bus, inv, impl = setup
        asset = _add_asset(state, inv, "inst_c", "charge_asset", {"charges": 1})
        ctx = _success_ctx(state, skill=Skill.COMBAT, source="inst_weapon")
        bus.emit(ctx)
        assert asset.uses["charges"] == 1

    def test_no_placement_without_commit(self, setup):
        state, bus, inv, impl = setup
        asset = _add_asset(state, inv, "inst_c", "charge_asset", {"charges": 1})
        ctx = _success_ctx(state)
        ctx.committed_cards = ["guts_lv0"]
        bus.emit(ctx)
        assert asset.uses["charges"] == 1

    def test_no_target_no_effect(self, setup):
        """没有带充能/秘密的支援时不触发。"""
        state, bus, inv, impl = setup
        ctx = _success_ctx(state)
        bus.emit(ctx)
        assert "enraptured_placed" not in ctx.extra
