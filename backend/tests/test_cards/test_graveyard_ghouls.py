"""Tests for Graveyard Ghouls (Level 0) — William Yorick signature weakness enemy."""

from backend.cards.neutral.graveyard_ghouls_lv0 import GraveyardGhouls
from backend.models.state import CardInstance
from backend.tests.conftest import make_enemy_data


def _setup(game, engaged=True):
    GraveyardGhouls("g1").register(game.event_bus, "g1")
    game.register_card_data(make_enemy_data(
        id="graveyard_ghouls_lv0", fight=3, health=3, evade=2,
        keywords=["hunter"],
    ))
    inv = game.state.get_investigator("test_investigator")
    ghoul = CardInstance(
        instance_id="gg1", card_id="graveyard_ghouls_lv0",
        owner_id="test_investigator", controller_id="scenario",
    )
    game.state.cards_in_play["gg1"] = ghoul
    if engaged:
        inv.threat_area.append("gg1")
    return inv, ghoul


class TestGraveyardGhouls:
    def test_discard_locked_while_engaged(self, game):
        """交战时弃牌堆锁定。"""
        _setup(game, engaged=True)
        impl = GraveyardGhouls("g1")
        assert impl.can_leave_discard(game.state, "test_investigator") is False

    def test_discard_unlocked_when_not_engaged(self, game):
        """未交战（在地点上）不锁定。"""
        _setup(game, engaged=False)
        impl = GraveyardGhouls("g1")
        assert impl.can_leave_discard(game.state, "test_investigator") is True

    def test_discard_unlocked_after_defeat(self, game):
        """被击败后锁定解除。"""
        inv, ghoul = _setup(game, engaged=True)
        impl = GraveyardGhouls("g1")
        game.damage_engine.deal_damage_to_enemy(
            "gg1", 3, investigator_id="test_investigator",
        )
        assert "gg1" not in game.state.cards_in_play
        assert impl.can_leave_discard(game.state, "test_investigator") is True
