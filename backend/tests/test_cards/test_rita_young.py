"""Tests for Rita Young investigator ability and elder sign."""

import pytest

from backend.cards.survivor.rita_young import RitaYoung
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import ChaosTokenType, GameEvent
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_enemy_data, make_investigator_data, make_location_data,
)


@pytest.fixture
def game():
    g = Game("test_rita")
    g.chaos_bag.seed(42)

    inv_data = make_investigator_data(id="rita_young", name="Rita Young", agility=5)
    g.register_card_data(inv_data)

    loc_data = make_location_data(connections=["loc_b"])
    g.register_card_data(loc_data)
    loc_b_data = make_location_data(id="loc_b", name="Location B", connections=["test_location"])
    g.register_card_data(loc_b_data)

    enemy_data = make_enemy_data(health=3)
    g.register_card_data(enemy_data)

    g.add_investigator("rita", inv_data, deck=["card_a"] * 10, starting_location="test_location")
    g.add_location("test_location", loc_data, clues=3)
    g.add_location("loc_b", loc_b_data, clues=1)
    return g


@pytest.fixture
def impl(game):
    impl = RitaYoung("test_instance")
    impl.register(game.event_bus, "test_instance")
    return impl


def _add_enemy(game, instance_id="enemy_1"):
    enemy = CardInstance(
        instance_id=instance_id, card_id="test_enemy",
        owner_id="scenario", controller_id="scenario",
    )
    game.state.cards_in_play[instance_id] = enemy
    game.state.locations["test_location"].enemies.append(instance_id)
    return enemy


def _emit(game, event, **kwargs):
    ctx = EventContext(game_state=game.state, event=event, **kwargs)
    game.event_bus.emit(ctx)
    return ctx


def _pending(game):
    return game.state.scenario.vars.get("pending_choice", {})


class TestRitaYoungReaction:
    def test_evade_offers_choice_and_damage_resolves(self, game, impl):
        """躲避敌人后提供二选一；选 damage 对该敌人造成1点伤害。"""
        enemy = _add_enemy(game)
        _emit(game, GameEvent.ENEMY_EVADED, investigator_id="rita", enemy_id="enemy_1")

        pending = _pending(game)
        assert pending.get("kind") == "rita_young_evade"
        assert pending.get("enemy_id") == "enemy_1"

        assert impl.resolve_evade_choice(game.state, "rita", "damage")
        assert enemy.damage == 1
        assert _pending(game) == {}

    def test_evade_move_choice_moves_to_connecting_location(self, game, impl):
        """选 move 移动到一个连接地点（缺省取第一个连接）。"""
        _add_enemy(game)
        inv = game.state.get_investigator("rita")
        _emit(game, GameEvent.ENEMY_EVADED, investigator_id="rita", enemy_id="enemy_1")

        assert impl.resolve_evade_choice(game.state, "rita", "move")
        assert inv.location_id == "loc_b"

    def test_move_rejects_non_connecting_destination(self, game, impl):
        """move 的目标必须是连接地点。"""
        _add_enemy(game)
        inv = game.state.get_investigator("rita")
        _emit(game, GameEvent.ENEMY_EVADED, investigator_id="rita", enemy_id="enemy_1")

        assert not impl.resolve_evade_choice(game.state, "rita", "move", destination="nowhere")
        assert inv.location_id == "test_location"

    def test_limit_once_per_round(self, game, impl):
        """每轮限1次：第二次躲避不提供选择；新轮重置。"""
        _add_enemy(game, "enemy_1")
        _add_enemy(game, "enemy_2")

        _emit(game, GameEvent.ENEMY_EVADED, investigator_id="rita", enemy_id="enemy_1")
        assert _pending(game).get("kind") == "rita_young_evade"
        impl.resolve_evade_choice(game.state, "rita", "decline")

        # 同轮第二次躲避：不触发
        _emit(game, GameEvent.ENEMY_EVADED, investigator_id="rita", enemy_id="enemy_2")
        assert _pending(game) == {}

        # 新一轮：重置
        _emit(game, GameEvent.ROUND_BEGINS)
        _emit(game, GameEvent.ENEMY_EVADED, investigator_id="rita", enemy_id="enemy_2")
        assert _pending(game).get("kind") == "rita_young_evade"

    def test_no_trigger_for_other_investigators(self, game, impl):
        """其他调查员躲避敌人不触发。"""
        other_data = make_investigator_data(id="other_inv", name="Other")
        game.register_card_data(other_data)
        game.add_investigator("other", other_data, deck=[], starting_location="test_location")
        _add_enemy(game)

        _emit(game, GameEvent.ENEMY_EVADED, investigator_id="other", enemy_id="enemy_1")
        assert _pending(game) == {}

    def test_damage_choice_can_defeat_enemy(self, game, impl):
        """damage 选项可击败残血敌人（进入遭遇弃牌堆）。"""
        enemy = _add_enemy(game)
        enemy.damage = 2  # health=3，再受1伤即击败

        _emit(game, GameEvent.ENEMY_EVADED, investigator_id="rita", enemy_id="enemy_1")
        assert impl.resolve_evade_choice(game.state, "rita", "damage")
        assert "enemy_1" not in game.state.cards_in_play
        assert "test_enemy" in game.state.scenario.encounter_discard


class TestRitaYoungElderSign:
    def test_elder_sign_plus_two(self, game, impl):
        """远古印记：+2。"""
        ctx = _emit(
            game, GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="rita", chaos_token=ChaosTokenType.ELDER_SIGN,
        )
        assert ctx.amount == 2

    def test_elder_sign_ignores_limit_until_round_ends(self, game, impl):
        """远古印记后本轮内忽略反应限次；轮结束时恢复。"""
        _add_enemy(game, "enemy_1")
        _add_enemy(game, "enemy_2")

        # 本轮已用过一次反应
        _emit(game, GameEvent.ENEMY_EVADED, investigator_id="rita", enemy_id="enemy_1")
        impl.resolve_evade_choice(game.state, "rita", "decline")
        _emit(game, GameEvent.ENEMY_EVADED, investigator_id="rita", enemy_id="enemy_2")
        assert _pending(game) == {}

        # 揭示远古印记：限次被忽略，可再次触发
        _emit(
            game, GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="rita", chaos_token=ChaosTokenType.ELDER_SIGN,
        )
        _emit(game, GameEvent.ENEMY_EVADED, investigator_id="rita", enemy_id="enemy_2")
        assert _pending(game).get("kind") == "rita_young_evade"
        impl.resolve_evade_choice(game.state, "rita", "decline")

        # 轮结束：忽略标记失效，限次重新生效（新一轮开始重置）
        _emit(game, GameEvent.ROUND_ENDS)
        _emit(game, GameEvent.ROUND_BEGINS)
        _emit(game, GameEvent.ENEMY_EVADED, investigator_id="rita", enemy_id="enemy_1")
        assert _pending(game).get("kind") == "rita_young_evade"
        impl.resolve_evade_choice(game.state, "rita", "decline")
        _emit(game, GameEvent.ENEMY_EVADED, investigator_id="rita", enemy_id="enemy_2")
        assert _pending(game) == {}

    def test_elder_sign_ignores_limit_before_first_use(self, game, impl):
        """远古印记后同轮可连续触发多次反应。"""
        _add_enemy(game, "enemy_1")
        _add_enemy(game, "enemy_2")
        _emit(
            game, GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="rita", chaos_token=ChaosTokenType.ELDER_SIGN,
        )
        _emit(game, GameEvent.ENEMY_EVADED, investigator_id="rita", enemy_id="enemy_1")
        assert _pending(game).get("kind") == "rita_young_evade"
        impl.resolve_evade_choice(game.state, "rita", "decline")
        _emit(game, GameEvent.ENEMY_EVADED, investigator_id="rita", enemy_id="enemy_2")
        assert _pending(game).get("kind") == "rita_young_evade"
