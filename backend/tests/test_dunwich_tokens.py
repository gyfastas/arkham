"""Tests for Dunwich Legacy scenario chaos token effects."""

from backend.engine.event_bus import EventContext
from backend.models.enums import ChaosTokenType, GameEvent
from backend.tests.conftest import make_asset_data
from backend.tests.test_scenario_tokens import _make_game, _token


def _fail(game, inv_id="player"):
    game.event_bus.emit(EventContext(
        game_state=game.state, event=GameEvent.SKILL_TEST_FAILED,
        investigator_id=inv_id, success=False,
    ))


def _succeed(game, inv_id="player"):
    game.event_bus.emit(EventContext(
        game_state=game.state, event=GameEvent.SKILL_TEST_SUCCESSFUL,
        investigator_id=inv_id, success=True,
    ))


class TestExtracurricularActivityTokens:
    def test_skull_minus1_and_discard3_on_fail(self):
        g, _ = _make_game("extracurricular_activity")
        inv = g.state.get_investigator("player")
        inv.deck = ["c1", "c2", "c3", "c4"]
        ctx = _token(g, ChaosTokenType.SKULL)
        assert ctx.amount == -1
        _fail(g)
        assert inv.deck == ["c4"]
        assert inv.discard == ["c1", "c2", "c3"]

    def test_cultist_scales_with_discard(self):
        g, _ = _make_game("extracurricular_activity")
        inv = g.state.get_investigator("player")
        inv.discard = ["x"] * 9
        ctx = _token(g, ChaosTokenType.CULTIST)
        assert ctx.amount == -1
        inv.discard = ["x"] * 10
        ctx = _token(g, ChaosTokenType.CULTIST)
        assert ctx.amount == -3

    def test_elder_thing_discard2_cost_sum(self):
        g, _ = _make_game("extracurricular_activity")
        g.register_card_data(make_asset_data(id="c1", cost=2))
        g.register_card_data(make_asset_data(id="c2", cost=3))
        g.register_card_data(make_asset_data(id="c5", cost=1))
        inv = g.state.get_investigator("player")
        inv.deck = ["c1", "c2", "c5"]
        ctx = _token(g, ChaosTokenType.ELDER_THING)
        assert ctx.amount == -5  # 2 + 3
        assert inv.deck == ["c5"]
        assert inv.discard == ["c1", "c2"]


class TestHouseAlwaysWinsTokens:
    def test_skull_autopays_resources(self):
        g, _ = _make_game("the_house_always_wins")
        inv = g.state.get_investigator("player")
        inv.resources = 3
        ctx = _token(g, ChaosTokenType.SKULL)
        assert ctx.amount == 0
        assert inv.resources == 1

    def test_skull_minus2_without_resources(self):
        g, _ = _make_game("the_house_always_wins")
        inv = g.state.get_investigator("player")
        inv.resources = 1
        ctx = _token(g, ChaosTokenType.SKULL)
        assert ctx.amount == -2
        assert inv.resources == 1

    def test_cultist_gain3_on_success(self):
        g, _ = _make_game("the_house_always_wins")
        inv = g.state.get_investigator("player")
        inv.resources = 0
        ctx = _token(g, ChaosTokenType.CULTIST)
        assert ctx.amount == -3
        _succeed(g)
        assert inv.resources == 3

    def test_tablet_lose3_on_fail(self):
        g, _ = _make_game("the_house_always_wins")
        inv = g.state.get_investigator("player")
        inv.resources = 5
        ctx = _token(g, ChaosTokenType.TABLET)
        assert ctx.amount == -2
        _fail(g)
        assert inv.resources == 2


class TestMiskatonicMuseumTokens:
    def test_tablet_returns_clue_to_location(self):
        g, _ = _make_game("the_miskatonic_museum")
        inv = g.state.get_investigator("player")
        loc = g.state.get_location("test_location")
        inv.clues = 2
        loc.clues = 1
        ctx = _token(g, ChaosTokenType.TABLET)
        assert ctx.amount == -2
        _fail(g)
        assert inv.clues == 1
        assert loc.clues == 2


class TestEssexCountyExpressTokens:
    def test_skull_is_agenda_number(self):
        g, _ = _make_game("essex_county_express")
        g.state.scenario.current_agenda_index = 0
        ctx = _token(g, ChaosTokenType.SKULL)
        assert ctx.amount == -1
        g.state.scenario.current_agenda_index = 1
        ctx = _token(g, ChaosTokenType.SKULL)
        assert ctx.amount == -2

    def test_cultist_fail_loses_actions(self):
        g, _ = _make_game("essex_county_express")
        inv = g.state.get_investigator("player")
        inv.actions_remaining = 3
        ctx = _token(g, ChaosTokenType.CULTIST)
        assert ctx.amount == -1
        _fail(g)
        assert inv.actions_remaining == 0


class TestWhereDoomAwaitsTokens:
    def test_skull_minus3_in_spectral(self):
        g, _ = _make_game("where_doom_awaits")
        loc = g.state.get_location("test_location")
        loc.card_data.traits = []
        ctx = _token(g, ChaosTokenType.SKULL)
        assert ctx.amount == -1
        loc.card_data.traits = ["幻境"]
        ctx = _token(g, ChaosTokenType.SKULL)
        assert ctx.amount == -3

    def test_tablet_scales_with_agenda(self):
        g, _ = _make_game("where_doom_awaits")
        g.state.scenario.current_agenda_index = 0
        ctx = _token(g, ChaosTokenType.TABLET)
        assert ctx.amount == -2
        g.state.scenario.current_agenda_index = 1
        ctx = _token(g, ChaosTokenType.TABLET)
        assert ctx.amount == -4


class TestLostInTimeAndSpaceTokens:
    def test_skull_per_extradimensional_location(self):
        g, _ = _make_game("lost_in_time_and_space")
        loc = g.state.get_location("test_location")
        loc.card_data.traits = ["異次元"]
        ctx = _token(g, ChaosTokenType.SKULL)
        assert ctx.amount == -1

    def test_elder_thing_is_shroud(self):
        g, _ = _make_game("lost_in_time_and_space")
        ctx = _token(g, ChaosTokenType.ELDER_THING)
        # test_location shroud = 2 (make_location_data default)
        assert ctx.amount == -2
