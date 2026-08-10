"""Tests for Infighting (Level 3)."""

import pytest
from backend.cards.survivor.infighting_lv3 import Infighting
from backend.models.enums import GameEvent, PlayerClass
from backend.engine.event_bus import EventContext
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_enemy_data, make_event_data, make_investigator_data,
    make_location_data,
)
from backend.engine.game import Game


def _emit(game, event, inv_id="inv1", **kwargs):
    ctx = EventContext(
        game_state=game.state, event=event, investigator_id=inv_id, **kwargs)
    game.event_bus.emit(ctx)
    return ctx


def _add_enemy(game, instance_id, card_id):
    enemy = CardInstance(
        instance_id=instance_id, card_id=card_id,
        owner_id="scenario", controller_id="scenario",
    )
    game.state.cards_in_play[instance_id] = enemy
    return enemy


@pytest.fixture
def game():
    g = Game("test")
    inv_data = make_investigator_data()
    g.register_card_data(inv_data)
    loc = make_location_data()
    g.register_card_data(loc)
    g.register_card_data(make_event_data(
        id="infighting_lv3", name="Infighting", cost=1,
        card_class=PlayerClass.SURVIVOR, fast=True,
    ))
    g.register_card_data(make_enemy_data(id="ghoul"))
    g.register_card_data(make_enemy_data(id="elite_monster", keywords=["elite"]))
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)
    g.card_registry.register_class(Infighting)
    impl = Infighting("impl_1")
    impl.register(g.event_bus, "impl_1")
    _add_enemy(g, "ghoul_1", "ghoul")
    _add_enemy(g, "ghoul_2", "ghoul")
    _add_enemy(g, "elite_1", "elite_monster")
    return g


class TestInfighting:
    def test_card_registered(self, game):
        assert "infighting_lv3" in game.card_registry.registered_cards

    def test_auto_plays_and_cancels_first_non_elite_attack(self, game):
        """非精英敌人攻击你时自动打出（付费、入弃牌堆）并取消攻击。"""
        inv = game.state.get_investigator("inv1")
        inv.hand = ["infighting_lv3"]
        inv.resources = 1

        ctx = _emit(game, GameEvent.ENEMY_ATTACKS, enemy_id="ghoul_1")
        assert ctx.cancelled is True
        assert "infighting_lv3" in inv.discard
        assert "infighting_lv3" not in inv.hand
        assert inv.resources == 0

    def test_cancels_subsequent_attacks_this_phase(self, game):
        """打出后本阶段其余非精英攻击也取消（无需再付费）。"""
        inv = game.state.get_investigator("inv1")
        inv.hand = ["infighting_lv3"]
        inv.resources = 1

        _emit(game, GameEvent.ENEMY_ATTACKS, enemy_id="ghoul_1")
        ctx = _emit(game, GameEvent.ENEMY_ATTACKS, enemy_id="ghoul_2")
        assert ctx.cancelled is True
        assert inv.resources == 0  # 未再付费

    def test_elite_attack_not_cancelled(self, game):
        """精英敌人的攻击不取消（也不触发打出）。"""
        inv = game.state.get_investigator("inv1")
        inv.hand = ["infighting_lv3"]
        inv.resources = 1

        ctx = _emit(game, GameEvent.ENEMY_ATTACKS, enemy_id="elite_1")
        assert ctx.cancelled is False
        assert "infighting_lv3" in inv.hand
        assert inv.resources == 1

    def test_expires_at_enemy_phase_end(self, game):
        """阶段结束后效果过期（手牌无卡时不再取消）。"""
        inv = game.state.get_investigator("inv1")
        inv.hand = ["infighting_lv3"]
        inv.resources = 1

        _emit(game, GameEvent.ENEMY_ATTACKS, enemy_id="ghoul_1")
        _emit(game, GameEvent.ENEMY_PHASE_ENDS)

        ctx = _emit(game, GameEvent.ENEMY_ATTACKS, enemy_id="ghoul_2")
        assert ctx.cancelled is False

    def test_no_trigger_without_card_in_hand(self, game):
        inv = game.state.get_investigator("inv1")
        inv.hand = []
        ctx = _emit(game, GameEvent.ENEMY_ATTACKS, enemy_id="ghoul_1")
        assert ctx.cancelled is False
