"""Tests for the location attachment architecture (上锁的门 / 遮蔽迷雾)."""

import pytest

from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import ChaosTokenType, GameEvent, Skill
from backend.scenarios.official_core import ScenarioController
from backend.tests.conftest import make_investigator_data, make_location_data


def _make_game():
    g = Game("test_attach")
    g.chaos_bag.seed(42)
    inv_data = make_investigator_data(combat=4, agility=4)
    g.register_card_data(inv_data)
    loc1 = make_location_data(id="loc1", shroud=2, clue_value=1, connections=["loc2"])
    loc2 = make_location_data(id="loc2", shroud=3, clue_value=3, connections=["loc1"])
    g.register_card_data(loc1)
    g.register_card_data(loc2)
    g.add_investigator("player", inv_data, starting_location="loc1", deck=["c1"] * 10)
    g.add_location("loc1", loc1, clues=1)
    g.add_location("loc2", loc2, clues=3)
    g.setup()
    ctrl = ScenarioController(g, action_log=[])
    ctrl.attach()
    return g, ctrl


class TestAttachmentAPI:
    def test_attach_and_query(self):
        g, ctrl = _make_game()
        iid = ctrl.attach_card_to_location("locked_door", "loc2")
        assert iid is not None
        loc = g.state.get_location("loc2")
        assert iid in loc.attachments
        assert ctrl.location_attachment_ids("loc2") == ["locked_door"]
        assert ctrl.location_with_attachment("locked_door") == "loc2"
        assert ctrl.location_investigate_blocker("loc2") == "locked_door"
        assert ctrl.location_investigate_blocker("loc1") is None

    def test_detach_moves_to_encounter_discard(self):
        g, ctrl = _make_game()
        iid = ctrl.attach_card_to_location("locked_door", "loc2")
        ctrl.detach_card_from_location(iid)
        loc = g.state.get_location("loc2")
        assert iid not in loc.attachments
        assert iid not in g.state.cards_in_play
        assert "locked_door" in g.state.scenario.encounter_discard
        assert ctrl.location_investigate_blocker("loc2") is None

    def test_fog_shroud_bonus(self):
        g, ctrl = _make_game()
        assert ctrl.location_shroud_bonus("loc1") == 0
        ctrl.attach_card_to_location("obscuring_fog", "loc1")
        assert ctrl.location_shroud_bonus("loc1") == 2

    def test_fog_discarded_on_successful_investigate(self):
        g, ctrl = _make_game()
        iid = ctrl.attach_card_to_location("obscuring_fog", "loc1")
        g.event_bus.emit(EventContext(
            game_state=g.state, event=GameEvent.CLUE_DISCOVERED,
            investigator_id="player", location_id="loc1", amount=1,
        ))
        loc = g.state.get_location("loc1")
        assert iid not in loc.attachments
        assert ctrl.location_shroud_bonus("loc1") == 0


class TestLockedDoorFlow:
    def test_draw_attaches_to_most_clues_location(self):
        g, ctrl = _make_game()
        # loc2 has 3 clues, loc1 has 1 → attaches to loc2
        result = ctrl.resolve_encounter_card("locked_door", investigator_id="player")
        assert not result.get("pending")
        assert ctrl.location_with_attachment("locked_door") == "loc2"
        assert ctrl.location_investigate_blocker("loc2") == "locked_door"

    def _session(self, g, ctrl):
        from server.game_session import GameSession
        session = GameSession.__new__(GameSession)
        session.game = g
        session.controller = ctrl
        session.action_log = []
        session.game_over = None
        return session

    def test_unlock_requires_being_at_location(self):
        g, ctrl = _make_game()
        ctrl.resolve_encounter_card("locked_door", investigator_id="player")
        session = self._session(g, ctrl)
        inv = g.state.get_investigator("player")
        inv.actions_remaining = 3
        # 调查员在 loc1，门在 loc2 → 拒绝
        result = session._locked_door_test(inv, {"skill": "combat"})
        assert not result["success"]
        assert "所在地点" in result["message"]

    def test_unlock_success_detaches(self):
        g, ctrl = _make_game()
        ctrl.resolve_encounter_card("locked_door", investigator_id="player")
        session = self._session(g, ctrl)
        inv = g.state.get_investigator("player")
        inv.actions_remaining = 3
        inv.location_id = "loc2"  # 走到门前
        g.chaos_bag.tokens = [ChaosTokenType.PLUS_1]  # combat 4+1 vs 难度3 → 成功
        result = session._locked_door_test(inv, {"skill": "combat", "committed_cards": []})
        assert result["success"]
        assert ctrl.location_with_attachment("locked_door") is None
        assert inv.actions_remaining == 2

    def test_unlock_failure_keeps_door(self):
        g, ctrl = _make_game()
        ctrl.resolve_encounter_card("locked_door", investigator_id="player")
        session = self._session(g, ctrl)
        inv = g.state.get_investigator("player")
        inv.actions_remaining = 3
        inv.location_id = "loc2"
        g.chaos_bag.tokens = [ChaosTokenType.AUTO_FAIL]
        result = session._locked_door_test(inv, {"skill": "agility", "committed_cards": []})
        assert not result["success"]
        assert ctrl.location_with_attachment("locked_door") == "loc2"
