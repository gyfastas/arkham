"""Tests for Jenny Barnes investigator ability."""

import pytest
from backend.cards.rogue.jenny_barnes import JennyBarnes
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import ChaosTokenType, GameEvent, Phase
from backend.tests.conftest import make_investigator_data, make_location_data


@pytest.fixture
def game():
    g = Game("test_jenny")
    g.chaos_bag.seed(42)

    inv_data = make_investigator_data(id="jenny_barnes", name="Jenny Barnes")
    g.register_card_data(inv_data)

    loc_data = make_location_data()
    g.register_card_data(loc_data)

    deck = ["card_a", "card_b", "card_c", "card_d", "card_e"] * 3
    g.add_investigator("jenny", inv_data, deck=deck, starting_location="test_location")
    g.add_location("test_location", loc_data, clues=3)

    return g


@pytest.fixture
def impl(game):
    impl = JennyBarnes("test_instance")
    impl.register(game.event_bus, "test_instance")
    return impl


def _emit(game, event, **kwargs):
    ctx = EventContext(game_state=game.state, event=event, **kwargs)
    game.event_bus.emit(ctx)
    return ctx


class TestJennyBarnes:
    def test_bonus_resource_during_upkeep(self, game, impl):
        """每个补给阶段额外获得1个资源（每阶段限1次，下一补给阶段重置）。"""
        inv = game.state.get_investigator("jenny")
        inv.resources = 5
        game.state.scenario.current_phase = Phase.UPKEEP

        _emit(game, GameEvent.UPKEEP_PHASE_BEGINS)
        _emit(game, GameEvent.RESOURCES_GAINED, investigator_id="jenny", amount=1)
        assert inv.resources == 6

        # 同一补给阶段再次获得资源：不再加成
        _emit(game, GameEvent.RESOURCES_GAINED, investigator_id="jenny", amount=1)
        assert inv.resources == 6

        # 下一个补给阶段：重置
        _emit(game, GameEvent.UPKEEP_PHASE_BEGINS)
        _emit(game, GameEvent.RESOURCES_GAINED, investigator_id="jenny", amount=1)
        assert inv.resources == 7

    def test_no_bonus_outside_upkeep(self, game, impl):
        """非补给阶段获得资源时不触发。"""
        inv = game.state.get_investigator("jenny")
        inv.resources = 5
        game.state.scenario.current_phase = Phase.INVESTIGATION

        _emit(game, GameEvent.RESOURCES_GAINED, investigator_id="jenny", amount=1)
        assert inv.resources == 5

    def test_no_bonus_for_other_investigators(self, game, impl):
        """其他调查员在补给阶段不获得加成。"""
        other_data = make_investigator_data(id="other_investigator", name="Other")
        game.register_card_data(other_data)
        game.add_investigator("other", other_data, deck=[], starting_location="test_location")
        other = game.state.get_investigator("other")
        other.resources = 5
        game.state.scenario.current_phase = Phase.UPKEEP

        _emit(game, GameEvent.UPKEEP_PHASE_BEGINS)
        _emit(game, GameEvent.RESOURCES_GAINED, investigator_id="other", amount=1)
        assert other.resources == 5

    def test_elder_sign_bonus_per_resource(self, game, impl):
        """远古印记：每持有1个资源 +1。"""
        inv = game.state.get_investigator("jenny")
        inv.resources = 4

        ctx = _emit(
            game, GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="jenny", chaos_token=ChaosTokenType.ELDER_SIGN,
        )
        assert ctx.amount == 4
