"""Tests for Nkosi Mabati (Level 3). (08091)

入场后说出印记符号；同地点调查员揭示教徒/石板/古老者时横置：
改为揭示印记。
"""

import pytest
from backend.cards.guardian.nkosi_mabati_lv3 import NkosiMabati
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import (
    ChaosTokenType, GameEvent, PlayerClass, Skill, SlotType,
)
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_asset_data, make_investigator_data, make_location_data,
)


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)
    inv_data = make_investigator_data()
    g.register_card_data(inv_data)
    inv_data2 = make_investigator_data(id="inv2_card", name="Second")
    g.register_card_data(inv_data2)
    loc_a = make_location_data(id="loc_a", name="A", connections=["loc_b"])
    loc_b = make_location_data(id="loc_b", name="B", connections=["loc_a"])
    g.register_card_data(loc_a)
    g.register_card_data(loc_b)
    g.register_card_data(make_asset_data(
        id="nkosi_mabati_lv3", name="Nkosi Mabati", cost=4,
        card_class=PlayerClass.GUARDIAN, slots=[SlotType.ALLY],
        traits=["ally", "sorcerer"], health=2, sanity=2,
    ))
    g.add_investigator("inv1", inv_data, starting_location="loc_a")
    g.add_investigator("inv2", inv_data2, starting_location="loc_b")
    g.add_location("loc_a", loc_a, clues=0)
    g.add_location("loc_b", loc_b, clues=0)
    g.card_registry.register_class(NkosiMabati)

    inv = g.state.get_investigator("inv1")
    inst = CardInstance(
        instance_id="nkosi_1", card_id="nkosi_mabati_lv3",
        owner_id="inv1", controller_id="inv1", slot_used=[SlotType.ALLY],
    )
    g.state.cards_in_play["nkosi_1"] = inst
    inv.play_area.append("nkosi_1")
    g.card_registry.activate_card("nkosi_mabati_lv3", "nkosi_1", g.event_bus)
    return g


def _enters_play(game, **extra):
    ctx = EventContext(
        game_state=game.state, event=GameEvent.CARD_ENTERS_PLAY,
        investigator_id="inv1", target="nkosi_1",
        extra={"card_id": "nkosi_mabati_lv3", **extra},
    )
    game.event_bus.emit(ctx)
    return ctx


def _reveal(game, token, investigator_id="inv1"):
    ctx = EventContext(
        game_state=game.state, event=GameEvent.CHAOS_TOKEN_RESOLVED,
        investigator_id=investigator_id, skill_type=Skill.WILLPOWER,
        chaos_token=token, amount=0,
    )
    game.event_bus.emit(ctx)
    return ctx


class TestNkosiMabati:
    def test_sigil_named_on_enter(self, game):
        """入场默认印记为骷髅；可指定。"""
        ctx = _enters_play(game)
        assert ctx.extra["nkosi_sigil"] == "skull"

    def test_swaps_trigger_token_for_sigil(self, game):
        """同地点调查员揭示教徒：横置并改为印记（骷髅）。"""
        _enters_play(game, sigil="skull")
        ctx = _reveal(game, ChaosTokenType.CULTIST)
        assert ctx.chaos_token == ChaosTokenType.SKULL
        assert ctx.extra["nkosi_swapped"] == "cultist"
        assert game.state.get_card_instance("nkosi_1").exhausted is True

    def test_no_swap_when_exhausted(self, game):
        """已横置：不换标记。"""
        _enters_play(game)
        game.state.get_card_instance("nkosi_1").exhausted = True
        ctx = _reveal(game, ChaosTokenType.TABLET)
        assert ctx.chaos_token == ChaosTokenType.TABLET

    def test_no_swap_for_investigator_elsewhere(self, game):
        """其他地点的调查员揭示触发符号：不换。"""
        _enters_play(game)
        ctx = _reveal(game, ChaosTokenType.ELDER_THING, investigator_id="inv2")
        assert ctx.chaos_token == ChaosTokenType.ELDER_THING
        assert game.state.get_card_instance("nkosi_1").exhausted is False

    def test_no_swap_for_non_trigger_token(self, game):
        """揭示骷髅（非触发符号）：不换。"""
        _enters_play(game)
        ctx = _reveal(game, ChaosTokenType.SKULL)
        assert ctx.chaos_token == ChaosTokenType.SKULL
        assert "nkosi_swapped" not in ctx.extra
