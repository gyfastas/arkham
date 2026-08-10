"""Tests for Astounding Revelation (Level 0). (06023)

[反应]检索牌堆时本卡在被检索卡中：丢弃它，获得2资源或放置1秘密。
"""

import pytest

from backend.cards.seeker.astounding_revelation_lv0 import AstoundingRevelation
from backend.engine.event_bus import EventBus
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
        resources=1,
    )
    state.card_database["astounding_revelation_lv0"] = make_event_data(
        id="astounding_revelation_lv0", name="Astounding Revelation")
    inv.deck = ["card_a", "astounding_revelation_lv0", "card_b"]
    state.investigators["inv1"] = inv

    impl = AstoundingRevelation("inst_ar")
    impl.register(bus, "inst_ar")
    return state, bus, inv, impl


class TestAstoundingRevelation:
    def test_searched_gains_2_resources(self, setup):
        """检索中被发现：从牌堆丢弃，获得2资源。"""
        state, bus, inv, impl = setup
        searched = inv.deck[:2]  # 含 astounding_revelation
        assert impl.on_searched(state, "inv1", searched) is True
        assert "astounding_revelation_lv0" in inv.discard
        assert "astounding_revelation_lv0" not in inv.deck
        assert inv.resources == 3

    def test_searched_places_secret(self, setup):
        """选择放置秘密：你控制的资产上+1秘密。"""
        state, bus, inv, impl = setup
        state.card_database["stone"] = make_asset_data(
            id="stone", uses={"secrets": 0})
        stone = CardInstance(
            instance_id="inst_stone", card_id="stone",
            owner_id="inv1", controller_id="inv1",
        )
        stone.uses = {"secrets": 0}
        state.cards_in_play["inst_stone"] = stone
        inv.play_area.append("inst_stone")

        assert impl.on_searched(state, "inv1", inv.deck[:2],
                                choose="secret") is True
        assert stone.uses["secrets"] == 1
        assert inv.resources == 1  # 未获得资源

    def test_not_among_searched_no_effect(self, setup):
        state, bus, inv, impl = setup
        assert impl.on_searched(state, "inv1", ["card_a"]) is False
        assert "astounding_revelation_lv0" in inv.deck
        assert inv.resources == 1
