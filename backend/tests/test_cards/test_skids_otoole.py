"""Tests for Skids O'Toole investigator ability."""

import pytest
from backend.cards.rogue.skids_otoole import SkidsOToole
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import ChaosTokenType, GameEvent
from backend.tests.conftest import make_investigator_data, make_location_data


@pytest.fixture
def game():
    g = Game("test_skids")
    g.chaos_bag.seed(42)

    inv_data = make_investigator_data(id="skids_otoole", name="Skids O'Toole")
    g.register_card_data(inv_data)

    loc_data = make_location_data()
    g.register_card_data(loc_data)

    deck = ["card_a", "card_b", "card_c", "card_d", "card_e"] * 3
    g.add_investigator("skids", inv_data, deck=deck, starting_location="test_location")
    g.add_location("test_location", loc_data, clues=3)

    return g


@pytest.fixture
def impl(game):
    impl = SkidsOToole("test_instance")
    impl.register(game.event_bus, "test_instance")
    return impl


def _emit(game, event, **kwargs):
    ctx = EventContext(game_state=game.state, event=event, **kwargs)
    game.event_bus.emit(ctx)
    return ctx


class TestSkidsOToole:
    def test_extra_action_once_per_turn(self, game, impl):
        """回合中花2资源获得额外行动；每回合限1次，下回合重置。"""
        inv = game.state.get_investigator("skids")
        inv.resources = 5
        inv.actions_remaining = 3

        # 非自己回合不能发动
        assert impl.activate_extra_action(game.state, "skids") is False

        _emit(game, GameEvent.INVESTIGATOR_TURN_BEGINS, investigator_id="skids")

        assert impl.activate_extra_action(game.state, "skids") is True
        assert inv.resources == 3
        assert inv.actions_remaining == 4

        # 每回合限1次
        assert impl.activate_extra_action(game.state, "skids") is False
        assert inv.resources == 3
        assert inv.actions_remaining == 4

        # 回合结束 -> 新回合：限次重置
        _emit(game, GameEvent.INVESTIGATOR_TURN_ENDS, investigator_id="skids")
        _emit(game, GameEvent.INVESTIGATOR_TURN_BEGINS, investigator_id="skids")
        assert impl.activate_extra_action(game.state, "skids") is True
        assert inv.resources == 1
        assert inv.actions_remaining == 5

        # 资源不足时不能发动
        assert impl.activate_extra_action(game.state, "skids") is False

    def test_extra_action_not_for_other_investigators(self, game, impl):
        """其他调查员不能发动 Skids 的能力。"""
        other_data = make_investigator_data(id="other_investigator", name="Other")
        game.register_card_data(other_data)
        game.add_investigator("other", other_data, deck=[], starting_location="test_location")

        _emit(game, GameEvent.INVESTIGATOR_TURN_BEGINS, investigator_id="other")
        assert impl.activate_extra_action(game.state, "other") is False

    def test_elder_sign_plus_two_and_resources_on_success(self, game, impl):
        """远古印记：+2；检定成功获得2资源。"""
        inv = game.state.get_investigator("skids")
        inv.resources = 1

        ctx = _emit(
            game, GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="skids", chaos_token=ChaosTokenType.ELDER_SIGN,
        )
        assert ctx.amount == 2

        # 成功：+2资源
        _emit(game, GameEvent.SKILL_TEST_SUCCESSFUL, investigator_id="skids")
        assert inv.resources == 3

        # 再次远古印记但检定失败：不获得资源
        _emit(
            game, GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="skids", chaos_token=ChaosTokenType.ELDER_SIGN,
        )
        _emit(game, GameEvent.SKILL_TEST_FAILED, investigator_id="skids")
        assert inv.resources == 3
