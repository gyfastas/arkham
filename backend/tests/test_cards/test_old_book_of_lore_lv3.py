"""Tests for Old Book of Lore (Level 3)."""

import pytest
from backend.cards.seeker.old_book_of_lore_lv3 import OldBookOfLoreLv3
from backend.engine.event_bus import EventBus
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

    book_data = make_asset_data(
        id="old_book_of_lore_lv3", name="Old Book of Lore",
        traits=["item", "tome"], skill_icons={"willpower": 1, "intellect": 1},
        uses={"secrets": 2},
    )
    state.card_database["old_book_of_lore_lv3"] = book_data

    loc_data = make_location_data()
    state.card_database[loc_data.id] = loc_data

    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data,
        location_id="test_location",
        deck=["card_a", "card_b", "card_c", "card_d"],
    )
    state.investigators["inv1"] = inv
    state.locations["test_location"] = LocationState(
        location_id="test_location", card_data=loc_data, clues=2,
    )

    impl = OldBookOfLoreLv3("inst_book3")
    impl.register(bus, "inst_book3")

    ci = CardInstance(
        instance_id="inst_book3", card_id="old_book_of_lore_lv3",
        owner_id="inv1", controller_id="inv1", uses={"secrets": 2},
    )
    state.cards_in_play["inst_book3"] = ci
    inv.play_area.append("inst_book3")

    return state, bus, inv, impl


class TestOldBookOfLoreLv3:
    def test_card_data(self):
        impl = OldBookOfLoreLv3("inst")
        assert impl.card_id == "old_book_of_lore_lv3"

    def test_activate_search_shuffle(self, setup):
        """消耗：查看顶3抽1（默认第1张），洗混牌库。"""
        state, bus, inv, impl = setup

        ok = impl.activate(state, "inv1")

        assert ok
        assert inv.hand == ["card_a"]
        assert len(inv.deck) == 3
        assert set(inv.deck) == {"card_b", "card_c", "card_d"}
        assert state.get_card_instance("inst_book3").exhausted is True
        # 秘密不因搜索段消耗（第二段"花秘密-2费打出"需会话层流程，见报告）
        assert state.get_card_instance("inst_book3").uses["secrets"] == 2

    def test_activate_pick_index(self, setup):
        state, bus, inv, impl = setup

        ok = impl.activate(state, "inv1", pick_index=2)

        assert ok
        assert inv.hand == ["card_c"]
        assert set(inv.deck) == {"card_a", "card_b", "card_d"}

    def test_activate_fails_when_exhausted(self, setup):
        state, bus, inv, impl = setup
        state.get_card_instance("inst_book3").exhausted = True

        assert impl.activate(state, "inv1") is False
        assert inv.hand == []
