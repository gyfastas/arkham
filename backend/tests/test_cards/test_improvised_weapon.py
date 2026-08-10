"""Tests for Improvised Weapon (Level 0)."""

import pytest
from backend.cards.survivor.improvised_weapon_lv0 import ImprovisedWeapon
from backend.models.enums import (
    Action, ChaosTokenType, GameEvent, PlayerClass,
)
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_enemy_data, make_event_data, make_investigator_data,
    make_location_data,
)
from backend.engine.event_bus import EventContext
from backend.engine.game import Game


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)
    inv_data = make_investigator_data(combat=3)
    g.register_card_data(inv_data)
    loc = make_location_data()
    g.register_card_data(loc)
    g.register_card_data(make_event_data(
        id="improvised_weapon_lv0", name="Improvised Weapon", cost=1,
        card_class=PlayerClass.SURVIVOR))
    g.register_card_data(make_enemy_data(fight=4, health=5, evade=3))
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)
    g.card_registry.register_class(ImprovisedWeapon)
    return g


def _spawn(game, iid="enemy_1"):
    game.state.cards_in_play[iid] = CardInstance(
        instance_id=iid, card_id="test_enemy",
        owner_id="scenario", controller_id="scenario",
    )
    game.state.get_investigator("inv1").threat_area.append(iid)
    return game.state.cards_in_play[iid]


class TestImprovisedWeapon:
    def test_card_registered(self, game):
        assert "improvised_weapon_lv0" in game.card_registry.registered_cards

    def test_fight_with_minus_1_fight(self, game):
        """攻击检定目标 -1 战斗值（战斗3对战斗4-1=3），成功造成1伤害。"""
        enemy = _spawn(game)
        inv = game.state.get_investigator("inv1")
        inv.hand = ["improvised_weapon_lv0"]
        inv.resources = 3
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]

        assert game.action_resolver.perform_action(
            "inv1", Action.PLAY, card_id="improvised_weapon_lv0") is True

        assert enemy.damage == 1

    def test_from_discard_deals_bonus_damage(self, game):
        """弃牌堆打出：本次攻击+1伤害（共2）。"""
        enemy = _spawn(game)
        inv = game.state.get_investigator("inv1")

        impl = ImprovisedWeapon("impl_weapon")
        impl.register(game.event_bus, "impl_weapon")
        impl.bind_chaos_bag(game.chaos_bag)
        game.chaos_bag.tokens = [ChaosTokenType.PLUS_1]  # 3+1=4 vs 3

        ctx = EventContext(
            game_state=game.state, event=GameEvent.CARD_PLAYED,
            investigator_id="inv1",
            extra={"card_id": "improvised_weapon_lv0",
                   "played_from_discard": True},
        )
        game.event_bus.emit(ctx)

        assert ctx.extra["improvised_weapon_success"] is True
        assert enemy.damage == 2

        # 洗回牌库扫尾
        inv.discard.append("improvised_weapon_lv0")
        game.event_bus.emit(EventContext(
            game_state=game.state, event=GameEvent.ROUND_ENDS))
        assert "improvised_weapon_lv0" in inv.deck
        assert "improvised_weapon_lv0" not in inv.discard

    def test_failed_attack_no_damage(self, game):
        enemy = _spawn(game)
        inv = game.state.get_investigator("inv1")
        inv.hand = ["improvised_weapon_lv0"]
        inv.resources = 3
        game.chaos_bag.tokens = [ChaosTokenType.AUTO_FAIL]

        game.action_resolver.perform_action(
            "inv1", Action.PLAY, card_id="improvised_weapon_lv0")

        assert enemy.damage == 0
