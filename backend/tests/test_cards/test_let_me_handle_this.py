"""Tests for "Let me handle this!" (Level 0). (03022)

快速。另一位调查员抽取非祸害遭遇卡后、结算前打出：
改为你被视为抽取了该遭遇卡；结算其显现效果时你每项技能+2。
"""

import pytest
from backend.cards.guardian.let_me_handle_this_lv0 import LetMeHandleThis
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import (
    ChaosTokenType, CardType, GameEvent, PlayerClass, Skill,
)
from backend.models.state import CardData
from backend.tests.conftest import (
    make_event_data, make_investigator_data, make_location_data,
)


def _treachery(id, keywords=None):
    return CardData(
        id=id, name=id, name_cn=id, type=CardType.TREACHERY,
        card_class=PlayerClass.NEUTRAL, keywords=keywords or [],
    )


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)

    inv_data = make_investigator_data(combat=3)
    g.register_card_data(inv_data)
    inv_data2 = make_investigator_data(id="inv2_card", name="Second")
    g.register_card_data(inv_data2)
    g.register_card_data(make_location_data())
    g.register_card_data(make_event_data(
        id="let_me_handle_this_lv0", name='"Let me handle this!"', cost=0,
        fast=True, card_class=PlayerClass.GUARDIAN,
    ))
    g.register_card_data(_treachery("frozen_in_fear"))
    g.register_card_data(_treachery("peril_treachery", keywords=["peril"]))

    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_investigator("inv2", inv_data2, starting_location="test_location")
    g.add_location("test_location", g.state.get_card_data("test_location"), clues=2)
    g.card_registry.register_class(LetMeHandleThis)

    inv1 = g.state.get_investigator("inv1")
    inv1.hand.append("let_me_handle_this_lv0")
    g.card_registry.activate_card("let_me_handle_this_lv0", "lmht_1", g.event_bus)
    return g


def _draw_encounter(game, drawer_id, card_id):
    ctx = EventContext(
        game_state=game.state, event=GameEvent.ENCOUNTER_CARD_DRAWN,
        investigator_id=drawer_id, extra={"card_id": card_id},
    )
    game.event_bus.emit(ctx)
    return ctx


class TestLetMeHandleThis:
    def test_redirects_and_grants_plus_2(self, game):
        """其他调查员抽非祸害遭遇：自动打出并重定向；持有者检定+2。"""
        inv1 = game.state.get_investigator("inv1")

        ctx = _draw_encounter(game, "inv2", "frozen_in_fear")
        assert ctx.extra["redirect_to"] == "inv1"
        redirect = game.state.scenario.vars["encounter_redirect"]
        assert redirect == {
            "card_id": "frozen_in_fear", "from": "inv2", "to": "inv1",
        }
        assert "let_me_handle_this_lv0" in inv1.discard

        # 结算显现效果期间：持有者的技能检定 +2
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]
        result = game.skill_test_engine.run_test(
            "inv1", Skill.COMBAT, difficulty=5,
        )
        assert result.modified_skill == 5  # 3 + 2
        assert result.success is True

        # 检定结束后标记清除：下一次检定不再加值
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]
        result2 = game.skill_test_engine.run_test(
            "inv1", Skill.COMBAT, difficulty=5,
        )
        assert result2.modified_skill == 3

    def test_not_triggered_for_peril(self, game):
        """祸害（peril）遭遇卡不触发。"""
        inv1 = game.state.get_investigator("inv1")
        ctx = _draw_encounter(game, "inv2", "peril_treachery")
        assert "redirect_to" not in ctx.extra
        assert "let_me_handle_this_lv0" in inv1.hand

    def test_not_triggered_for_own_draw(self, game):
        """持有者自己抽遭遇卡不触发（必须是另一位调查员）。"""
        inv1 = game.state.get_investigator("inv1")
        ctx = _draw_encounter(game, "inv1", "frozen_in_fear")
        assert "redirect_to" not in ctx.extra
        assert "let_me_handle_this_lv0" in inv1.hand
