"""Tests for card activation abilities in GameSession._activate_asset."""

import pytest
from unittest.mock import MagicMock

from backend.models.state import (
    GameState, InvestigatorState, LocationState, ScenarioState, CardInstance, CardData,
)
from backend.models.enums import CardType, PlayerClass, SlotType, Skill
from backend.engine.event_bus import EventBus
from backend.engine.game import Game
from backend.engine.skill_test import SkillTestEngine
from backend.engine.damage import DamageEngine
from backend.engine.actions import ActionResolver
from backend.models.chaos import ChaosBag
from backend.cards.registry import CardRegistry
from backend.tests.conftest import make_investigator_data, make_location_data, make_asset_data


def _make_session_like(state, game):
    """Create a minimal object that has the methods _activate_asset and _resolve_choice need."""
    from server.game_session import GameSession
    session = GameSession.__new__(GameSession)
    session.game = game
    session.action_log = []
    session.controller = None
    session.game_over = None
    session.event_logger = None
    return session


def _make_game_with_inv(deck=None, horror=0, hand=None):
    """Create a Game with one investigator and basic location."""
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()
    bag = ChaosBag()
    st = SkillTestEngine(state, bus, bag)
    de = DamageEngine(state, bus)
    registry = CardRegistry()
    resolver = ActionResolver(state, bus, st, de, {}, registry)

    inv_data = make_investigator_data(intellect=3, willpower=4)
    state.card_database[inv_data.id] = inv_data

    loc_data = make_location_data()
    state.card_database[loc_data.id] = loc_data

    inv = InvestigatorState(
        investigator_id="player",
        card_data=inv_data,
        location_id="test_location",
        deck=deck or [],
        hand=hand or [],
    )
    inv.horror = horror
    inv.actions_remaining = 3
    state.investigators["player"] = inv

    loc = LocationState(location_id="test_location", card_data=loc_data, clues=3)
    state.locations["test_location"] = loc

    game = Game.__new__(Game)
    game.state = state
    game.event_bus = bus
    game.skill_test_engine = st
    game.action_resolver = resolver
    game.damage_engine = de

    return game, inv, state


def _place_asset(state, inv, card_id, uses=None, **card_kwargs):
    """Register card data, create instance, put in play area."""
    cd = make_asset_data(id=card_id, uses=uses, **card_kwargs)
    state.card_database[card_id] = cd

    inst_id = f"inst_{card_id}"
    ci = CardInstance(
        instance_id=inst_id, card_id=card_id,
        owner_id="player", controller_id="player",
    )
    if uses:
        ci.uses = dict(uses)
    state.cards_in_play[inst_id] = ci
    inv.play_area.append(inst_id)
    return ci, inst_id


class TestMrRookActivation:
    def test_mr_rook_step1_shows_depth_choice(self):
        game, inv, state = _make_game_with_inv(deck=["a", "b", "c", "d", "e", "f", "g", "h", "i"])
        ci, inst_id = _place_asset(state, inv, "mr_rook_lv0", uses={"secrets": 3})
        session = _make_session_like(state, game)

        result = session._activate_asset(inv, {"instance_id": inst_id})
        assert result["success"] is True
        assert "需要做出选择" in result["message"]

        # Should have pending choice for depth
        pc = state.scenario.vars.get("pending_choice")
        assert pc is not None
        assert pc["kind"] == "asset_mr_rook_depth"
        assert ci.exhausted is True
        assert ci.uses["secrets"] == 2
        # Free action: actions should not have been spent
        assert inv.actions_remaining == 3

    def test_mr_rook_step2_picks_card(self):
        game, inv, state = _make_game_with_inv(deck=["card_a", "card_b", "card_c"])
        # Register card data for searchable cards
        for cid in ["card_a", "card_b", "card_c"]:
            state.card_database[cid] = make_asset_data(id=cid, name=cid)

        ci, inst_id = _place_asset(state, inv, "mr_rook_lv0", uses={"secrets": 3})
        session = _make_session_like(state, game)

        # Step 1: activate
        session._activate_asset(inv, {"instance_id": inst_id})
        # Step 2: choose depth 3
        result = session._resolve_choice({"choice_id": "3"})
        assert result["success"] is True
        pc = state.scenario.vars.get("pending_choice")
        assert pc is not None
        assert pc["kind"] == "asset_mr_rook_pick"

        # Step 3: pick card_b
        result = session._resolve_choice({"choice_id": "card_b"})
        assert result["success"] is True
        assert "card_b" in inv.hand

    def test_mr_rook_no_secrets(self):
        game, inv, state = _make_game_with_inv(deck=["a", "b", "c"])
        ci, inst_id = _place_asset(state, inv, "mr_rook_lv0", uses={"secrets": 0})
        session = _make_session_like(state, game)

        result = session._activate_asset(inv, {"instance_id": inst_id})
        assert result["success"] is False
        assert "秘密" in result["message"]

    def test_mr_rook_weakness_drawn(self):
        """If searched cards contain a weakness (treachery), it's also drawn."""
        game, inv, state = _make_game_with_inv(deck=["normal_card", "weakness_card", "card_c"])
        state.card_database["normal_card"] = make_asset_data(id="normal_card", name="Normal")
        # Create a treachery card as weakness
        weakness_data = CardData(
            id="weakness_card", name="Weakness", name_cn="弱点", type=CardType.TREACHERY,
        )
        state.card_database["weakness_card"] = weakness_data
        state.card_database["card_c"] = make_asset_data(id="card_c", name="Card C")

        ci, inst_id = _place_asset(state, inv, "mr_rook_lv0", uses={"secrets": 3})
        session = _make_session_like(state, game)

        # Activate → depth 3 → pick normal_card
        session._activate_asset(inv, {"instance_id": inst_id})
        session._resolve_choice({"choice_id": "3"})
        result = session._resolve_choice({"choice_id": "normal_card"})

        assert result["success"] is True
        assert "normal_card" in inv.hand
        assert "weakness_card" in inv.hand  # weakness forced draw


class TestClarityOfMindActivation:
    def test_heal_horror(self):
        game, inv, state = _make_game_with_inv(horror=3)
        ci, inst_id = _place_asset(state, inv, "clarity_of_mind_lv0", uses={"charges": 3})
        session = _make_session_like(state, game)

        result = session._activate_asset(inv, {"instance_id": inst_id})
        assert result["success"] is True
        assert inv.horror == 2
        assert ci.uses["charges"] == 2
        assert ci.exhausted is True

    def test_no_charges(self):
        game, inv, state = _make_game_with_inv(horror=3)
        ci, inst_id = _place_asset(state, inv, "clarity_of_mind_lv0", uses={"charges": 0})
        session = _make_session_like(state, game)

        result = session._activate_asset(inv, {"instance_id": inst_id})
        assert result["success"] is False

    def test_discard_when_empty(self):
        game, inv, state = _make_game_with_inv(horror=3)
        ci, inst_id = _place_asset(state, inv, "clarity_of_mind_lv0", uses={"charges": 1})
        session = _make_session_like(state, game)

        result = session._activate_asset(inv, {"instance_id": inst_id})
        assert result["success"] is True
        assert inv.horror == 2
        # Asset should be discarded since charges ran out
        assert inst_id not in inv.play_area


class TestRiteOfSeekingActivation:
    def test_investigate_with_willpower(self):
        game, inv, state = _make_game_with_inv()
        ci, inst_id = _place_asset(state, inv, "rite_of_seeking_lv0", uses={"charges": 3})
        session = _make_session_like(state, game)

        # Willpower 4 vs shroud 2 — with favorable token should succeed
        # Force success by setting chaos bag to always draw +1
        game.skill_test_engine.chaos_bag = ChaosBag(tokens=[1, 1, 1])

        loc = state.get_location("test_location")
        before_clues = loc.clues

        result = session._activate_asset(inv, {"instance_id": inst_id})
        # With +1 token, willpower 4 vs shroud 2 should succeed
        assert ci.uses["charges"] == 2
        assert ci.exhausted is True
        if result["success"]:
            # Should discover 2 clues (1 base + 1 bonus)
            assert inv.clues == 2
            assert loc.clues == before_clues - 2

    def test_no_charges(self):
        game, inv, state = _make_game_with_inv()
        ci, inst_id = _place_asset(state, inv, "rite_of_seeking_lv0", uses={"charges": 0})
        session = _make_session_like(state, game)

        result = session._activate_asset(inv, {"instance_id": inst_id})
        assert result["success"] is False


class TestLiquidCourageActivation:
    def test_heal_horror_basic(self):
        game, inv, state = _make_game_with_inv(horror=2)
        ci, inst_id = _place_asset(state, inv, "liquid_courage_lv0", uses={"supplies": 4})
        session = _make_session_like(state, game)

        result = session._activate_asset(inv, {"instance_id": inst_id})
        assert result["success"] is True
        assert inv.horror <= 1  # At least 1 horror healed
        assert ci.uses["supplies"] == 3

    def test_no_supplies(self):
        game, inv, state = _make_game_with_inv(horror=2)
        ci, inst_id = _place_asset(state, inv, "liquid_courage_lv0", uses={"supplies": 0})
        session = _make_session_like(state, game)

        result = session._activate_asset(inv, {"instance_id": inst_id})
        assert result["success"] is False

    def test_discard_when_empty(self):
        game, inv, state = _make_game_with_inv(horror=2)
        ci, inst_id = _place_asset(state, inv, "liquid_courage_lv0", uses={"supplies": 1})
        session = _make_session_like(state, game)

        result = session._activate_asset(inv, {"instance_id": inst_id})
        assert result["success"] is True
        assert inst_id not in inv.play_area
