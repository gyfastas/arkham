"""Tests for Research Librarian (Level 0).

官方规则：进场时检索牌库中的典籍牌，**由玩家选择**1张加入手牌，然后洗牌。
"""

import pytest
from backend.cards.seeker.research_librarian_lv0 import ResearchLibrarian
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent
from backend.models.state import GameState, InvestigatorState, LocationState, ScenarioState, CardInstance
from backend.tests.conftest import make_investigator_data, make_location_data, make_asset_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()

    inv_data = make_investigator_data()
    state.card_database[inv_data.id] = inv_data

    librarian_data = make_asset_data(
        id="research_librarian_lv0", name="Research Librarian",
        traits=["ally", "miskatonic"],
    )
    state.card_database["research_librarian_lv0"] = librarian_data

    tome_a = make_asset_data(id="old_book_of_lore", name="Old Book of Lore", traits=["tome"])
    tome_b = make_asset_data(id="medical_texts", name="Medical Texts", traits=["tome"])
    plain = make_asset_data(id="card_a", name="Card A", traits=["item"])
    state.card_database["old_book_of_lore"] = tome_a
    state.card_database["medical_texts"] = tome_b
    state.card_database["card_a"] = plain

    loc_data = make_location_data()
    state.card_database[loc_data.id] = loc_data

    inv = InvestigatorState(
        investigator_id="inv1",
        card_data=inv_data,
        location_id="test_location",
        deck=["card_a", "old_book_of_lore", "medical_texts"],
    )
    state.investigators["inv1"] = inv

    loc = LocationState(location_id="test_location", card_data=loc_data, clues=2)
    state.locations["test_location"] = loc

    impl = ResearchLibrarian("inst_librarian")
    impl.register(bus, "inst_librarian")

    ci = CardInstance(instance_id="inst_librarian", card_id="research_librarian_lv0", owner_id="inv1", controller_id="inv1")
    state.cards_in_play["inst_librarian"] = ci
    inv.play_area.append("inst_librarian")

    return state, bus, inv, impl


def _enter_play(state, bus):
    bus.emit(EventContext(
        game_state=state,
        event=GameEvent.CARD_ENTERS_PLAY,
        investigator_id="inv1",
        target="inst_librarian",
    ))


def _make_session(state):
    from server.game_session import GameSession
    session = GameSession.__new__(GameSession)
    session.action_log = []
    session.game_over = None
    session.event_logger = None

    class _G:
        pass

    g = _G()
    g.state = state
    session.game = g
    return session


class TestResearchLibrarian:
    def test_enters_play_prompts_choice(self, setup):
        """进场：不自动抽牌，而是给出 pending_choice 让玩家挑选典籍。"""
        state, bus, inv, impl = setup
        _enter_play(state, bus)

        # 不自动移动任何牌
        assert inv.hand == []
        assert inv.deck == ["card_a", "old_book_of_lore", "medical_texts"]

        pc = state.scenario.vars.get("pending_choice")
        assert pc is not None
        assert pc["kind"] == "search_tome"
        option_ids = {o["id"] for o in pc["options"]}
        # 只包含典籍，不含普通牌
        assert option_ids == {"old_book_of_lore", "medical_texts"}

    def test_resolve_choice_player_picks(self, setup):
        """玩家选择后：所选典籍进手牌，其余留在牌库并洗混。"""
        state, bus, inv, impl = setup
        _enter_play(state, bus)

        session = _make_session(state)
        result = session._resolve_choice({"choice_id": "medical_texts"})
        assert result["success"]

        assert inv.hand == ["medical_texts"]
        assert "medical_texts" not in inv.deck
        # 未选的典籍仍在牌库
        assert "old_book_of_lore" in inv.deck
        assert "card_a" in inv.deck
        assert sorted(inv.deck) == ["card_a", "old_book_of_lore"]
        assert "pending_choice" not in state.scenario.vars
        assert any("研究馆员" in m for m in session.action_log)

    def test_resolve_choice_rejects_non_tome(self, setup):
        """选择不在选项里的牌（非典籍）应失败，状态不变。"""
        state, bus, inv, impl = setup
        _enter_play(state, bus)

        session = _make_session(state)
        result = session._resolve_choice({"choice_id": "card_a"})
        assert not result["success"]
        assert inv.hand == []
        assert "card_a" in inv.deck

    def test_no_tome_in_deck(self, setup):
        """牌库无典籍：不弹选择，记录提示消息。"""
        state, bus, inv, impl = setup
        inv.deck = ["card_a", "card_a", "card_a"]

        _enter_play(state, bus)

        assert "pending_choice" not in state.scenario.vars
        msgs = state.scenario.vars.get("action_messages", [])
        assert any("没有典籍" in m for m in msgs)
