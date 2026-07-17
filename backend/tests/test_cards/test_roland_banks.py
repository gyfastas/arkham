"""Tests for Roland Banks investigator ability."""

import pytest
from backend.cards.guardian.roland_banks import RolandBanks
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import ChaosTokenType, GameEvent
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_enemy_data, make_investigator_data, make_location_data,
)


@pytest.fixture
def game():
    g = Game("test_roland")
    g.chaos_bag.seed(42)

    inv_data = make_investigator_data(id="roland_banks", name="Roland Banks")
    g.register_card_data(inv_data)

    loc_data = make_location_data()
    g.register_card_data(loc_data)

    enemy_data = make_enemy_data()
    g.register_card_data(enemy_data)

    deck = ["card_a", "card_b", "card_c", "card_d", "card_e"] * 3
    g.add_investigator("roland", inv_data, deck=deck, starting_location="test_location")
    g.add_location("test_location", loc_data, clues=3)

    return g


@pytest.fixture
def impl(game):
    impl = RolandBanks("test_instance")
    impl.register(game.event_bus, "test_instance")
    return impl


def _add_enemy(game, instance_id="enemy_1", owner_id="scenario"):
    enemy = CardInstance(
        instance_id=instance_id, card_id="test_enemy",
        owner_id=owner_id, controller_id=owner_id,
    )
    game.state.cards_in_play[instance_id] = enemy
    return enemy


class TestRolandBanks:
    def test_discover_clue_after_defeating_enemy(self, game, impl):
        """击败交战敌人后发现1个线索；每轮限1次，下一轮重置。"""
        inv = game.state.get_investigator("roland")
        loc = game.state.locations["test_location"]
        _add_enemy(game)
        inv.threat_area.append("enemy_1")

        # ENEMY_DEFEATED ctx 不带 investigator_id（与引擎一致）
        ctx = EventContext(
            game_state=game.state,
            event=GameEvent.ENEMY_DEFEATED,
            target="enemy_1",
        )
        game.event_bus.emit(ctx)

        assert inv.clues == 1
        assert loc.clues == 2

        # 同一轮再次击败：不再触发
        game.event_bus.emit(EventContext(
            game_state=game.state,
            event=GameEvent.ENEMY_DEFEATED,
            target="enemy_1",
        ))
        assert inv.clues == 1
        assert loc.clues == 2

        # 新一轮开始：限次重置
        game.event_bus.emit(EventContext(
            game_state=game.state, event=GameEvent.ROUND_BEGINS,
        ))
        game.event_bus.emit(EventContext(
            game_state=game.state,
            event=GameEvent.ENEMY_DEFEATED,
            target="enemy_1",
        ))
        assert inv.clues == 2
        assert loc.clues == 1

    def test_defeat_attributed_via_damage_dealt(self, game, impl):
        """未交战敌人被 Roland 伤害击败时也触发；被他人击败时不触发。"""
        other_data = make_investigator_data(id="other_investigator", name="Other")
        game.register_card_data(other_data)
        game.add_investigator("other", other_data, deck=[], starting_location="test_location")

        roland = game.state.get_investigator("roland")
        other = game.state.get_investigator("other")
        _add_enemy(game, "enemy_1")
        _add_enemy(game, "enemy_2")

        # Roland 对 enemy_1 造成致命伤害
        game.event_bus.emit(EventContext(
            game_state=game.state,
            event=GameEvent.DAMAGE_DEALT,
            target="enemy_1",
            investigator_id="roland",
            amount=3,
        ))
        game.event_bus.emit(EventContext(
            game_state=game.state,
            event=GameEvent.ENEMY_DEFEATED,
            target="enemy_1",
        ))
        assert roland.clues == 1

        # 下一轮：other 击败 enemy_2，Roland 不获得线索
        game.event_bus.emit(EventContext(
            game_state=game.state, event=GameEvent.ROUND_BEGINS,
        ))
        game.event_bus.emit(EventContext(
            game_state=game.state,
            event=GameEvent.DAMAGE_DEALT,
            target="enemy_2",
            investigator_id="other",
            amount=3,
        ))
        game.event_bus.emit(EventContext(
            game_state=game.state,
            event=GameEvent.ENEMY_DEFEATED,
            target="enemy_2",
        ))
        assert roland.clues == 1
        assert other.clues == 0

    def test_elder_sign_bonus_per_clue(self, game, impl):
        """远古印记：所在地点每有1个线索 +1。"""
        ctx = EventContext(
            game_state=game.state,
            event=GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="roland",
            chaos_token=ChaosTokenType.ELDER_SIGN,
        )
        game.event_bus.emit(ctx)
        assert ctx.amount == 3  # 地点有3个线索

        # 非远古印记 / 非 Roland 不触发
        ctx2 = EventContext(
            game_state=game.state,
            event=GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="roland",
            chaos_token=ChaosTokenType.SKULL,
            amount=-2,
        )
        game.event_bus.emit(ctx2)
        assert ctx2.amount == -2
