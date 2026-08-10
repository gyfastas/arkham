"""Tests for Mr. "Rook" (Level 0) — 卡文件路径（会话层两段流程见
test_card_activations.py::TestMrRookActivation）。"""

import pytest
from backend.cards.seeker.mr_rook_lv0 import MrRook
from backend.engine.event_bus import EventBus
from backend.models.enums import CardType
from backend.models.state import (
    CardData, CardInstance, GameState, InvestigatorState, ScenarioState,
)
from backend.tests.conftest import make_asset_data, make_investigator_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()

    inv_data = make_investigator_data()
    state.card_database[inv_data.id] = inv_data
    for cid in ["card_a", "card_b", "card_c", "card_d"]:
        state.card_database[cid] = make_asset_data(id=cid, name=cid)
    state.card_database["weak_card"] = CardData(
        id="weak_card", name="Weakness", name_cn="弱点", type=CardType.TREACHERY,
        subtype="weakness",
    )

    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data,
        location_id="test_location",
        deck=["card_a", "card_b", "card_c", "card_d"],
    )
    state.investigators["inv1"] = inv

    impl = MrRook("inst_rook")
    impl.register(bus, "inst_rook")

    ci = CardInstance(
        instance_id="inst_rook", card_id="mr_rook_lv0",
        owner_id="inv1", controller_id="inv1", uses={"secrets": 3},
    )
    state.cards_in_play["inst_rook"] = ci
    inv.play_area.append("inst_rook")

    return state, bus, inv, impl


class TestMrRook:
    def test_requires_explicit_pick(self, setup):
        """弃用自动选牌：未指定 pick 时不消耗、不抽取。"""
        state, bus, inv, impl = setup
        ci = state.get_card_instance("inst_rook")

        assert impl.activate(state, "inv1") is False
        assert ci.uses["secrets"] == 3
        assert ci.exhausted is False
        assert inv.hand == []
        assert inv.deck == ["card_a", "card_b", "card_c", "card_d"]

    def test_pick_draws_and_spends_secret(self, setup):
        """指定 pick：花1秘密+消耗，抽指定牌，其余洗回牌堆。"""
        state, bus, inv, impl = setup
        ci = state.get_card_instance("inst_rook")

        ok = impl.activate(state, "inv1", depth=3, pick="card_b")

        assert ok is True
        assert ci.uses["secrets"] == 2
        assert ci.exhausted is True
        assert inv.hand == ["card_b"]
        assert len(inv.deck) == 3
        assert set(inv.deck) == {"card_a", "card_c", "card_d"}

    def test_pick_outside_looked_range_rejected(self, setup):
        """pick 必须在查找范围内。"""
        state, bus, inv, impl = setup
        ci = state.get_card_instance("inst_rook")

        assert impl.activate(state, "inv1", depth=3, pick="card_d") is False
        assert ci.uses["secrets"] == 3
        assert inv.hand == []

    def test_weakness_forced_draw(self, setup):
        """查找中有弱点：除主选外强制抽1张弱点。"""
        state, bus, inv, impl = setup
        inv.deck = ["weak_card", "card_a", "card_b", "card_c"]

        ok = impl.activate(state, "inv1", depth=3, pick="card_a")

        assert ok is True
        assert "card_a" in inv.hand
        assert "weak_card" in inv.hand  # 弱点强制抽取

    def test_no_secrets_fails(self, setup):
        state, bus, inv, impl = setup
        state.get_card_instance("inst_rook").uses = {"secrets": 0}
        assert impl.activate(state, "inv1", pick="card_a") is False
