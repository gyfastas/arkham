"""Defeat detection: game_over must be set whenever the investigator is
defeated — including mid-action (retaliate / attacks of opportunity /
card effects), not only at end of turn."""

from backend.engine.game import Game
from backend.tests.conftest import make_investigator_data, make_location_data


def _make_session():
    from server.game_session import GameSession

    g = Game("test_defeat")
    inv_data = make_investigator_data()
    g.register_card_data(inv_data)
    loc = make_location_data()
    g.register_card_data(loc)
    g.add_investigator("player", inv_data, starting_location="test_location")
    g.add_location("test_location", loc)
    g.setup()

    session = GameSession.__new__(GameSession)
    session.game = g
    session.action_log = []
    session.game_over = None
    session.campaign = None
    session._campaign_settled = False
    return session


class TestDefeatGameOver:
    def test_damage_defeat_sets_game_over(self):
        session = _make_session()
        inv = session.game.state.get_investigator("player")
        assert session.game_over is None
        inv.damage = inv.health  # 伤害归零
        session._clear_game_over()
        assert session.game_over is not None
        assert session.game_over["type"] == "lose"
        # 单人局：唯一调查员被击败即全员败北
        assert "击败" in session.game_over["message"]

    def test_horror_defeat_sets_game_over(self):
        session = _make_session()
        inv = session.game.state.get_investigator("player")
        inv.horror = inv.sanity  # 恐惧归零
        session._clear_game_over()
        assert session.game_over is not None
        assert session.game_over["type"] == "lose"
        assert "击败" in session.game_over["message"]

    def test_no_defeat_no_game_over(self):
        session = _make_session()
        inv = session.game.state.get_investigator("player")
        inv.damage = 1
        session._clear_game_over()
        assert session.game_over is None

    def test_resolution_still_works(self):
        session = _make_session()
        session.game.state.scenario.vars["resolution_id"] = "R1"
        session._clear_game_over()
        assert session.game_over["type"] == "win"
