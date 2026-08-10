"""Tests for Daniela Reyes investigator ability."""

import pytest
from backend.cards.guardian.daniela_reyes import DanielaReyes
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import ChaosTokenType, GameEvent
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_enemy_data, make_investigator_data, make_location_data,
)


@pytest.fixture
def game():
    g = Game("test_daniela")
    g.chaos_bag.seed(42)

    inv_data = make_investigator_data(id="daniela_reyes", name="Daniela Reyes")
    g.register_card_data(inv_data)

    loc_data = make_location_data()
    g.register_card_data(loc_data)

    enemy_data = make_enemy_data()
    g.register_card_data(enemy_data)

    deck = ["card_a", "card_b", "card_c", "card_d", "card_e"] * 3
    g.add_investigator("daniela", inv_data, deck=deck,
                       starting_location="test_location")
    g.add_location("test_location", loc_data, clues=3)

    return g


@pytest.fixture
def impl(game):
    impl = DanielaReyes("test_instance")
    impl.register(game.event_bus, "test_instance")
    return impl


def _emit(game, event, **kwargs):
    ctx = EventContext(game_state=game.state, event=event, **kwargs)
    game.event_bus.emit(ctx)
    return ctx


def _add_enemy(game, instance_id="enemy_1", engaged=True):
    enemy = CardInstance(
        instance_id=instance_id, card_id="test_enemy",
        owner_id="scenario", controller_id="scenario",
    )
    game.state.cards_in_play[instance_id] = enemy
    if engaged:
        game.state.get_investigator("daniela").threat_area.append(instance_id)
    return enemy


class TestDanielaReaction:
    def test_pending_choice_on_enemy_attack(self, game, impl):
        """敌人攻击后：提供1伤害/自动躲避/不触发选项。"""
        _add_enemy(game)
        _emit(game, GameEvent.ENEMY_ATTACKS,
              investigator_id="daniela", enemy_id="enemy_1")
        pending = game.state.scenario.vars.get("pending_choice")
        assert pending is not None
        assert pending["kind"] == "daniela_reyes_reaction"
        assert pending["enemy_id"] == "enemy_1"
        option_ids = [o["id"] for o in pending["options"]]
        assert option_ids == ["damage", "evade", "decline"]

    def test_triggers_even_if_attack_cancelled(self, game, impl):
        """即使攻击被取消也触发（ctx.cancelled 不影响）。"""
        _add_enemy(game)
        ctx = EventContext(
            game_state=game.state, event=GameEvent.ENEMY_ATTACKS,
            investigator_id="daniela", enemy_id="enemy_1",
        )
        ctx.cancelled = False  # 由其他卡取消的情况：事件仍会送达 handler
        game.event_bus.emit(ctx)
        assert game.state.scenario.vars.get("pending_choice") is not None

    def test_aoo_does_not_trigger(self, game, impl):
        """趁乱攻击（ATTACK_OF_OPPORTUNITY）不触发。"""
        _add_enemy(game)
        _emit(game, GameEvent.ATTACK_OF_OPPORTUNITY,
              investigator_id="daniela", enemy_id="enemy_1")
        assert game.state.scenario.vars.get("pending_choice") is None

    def test_resolve_damage(self, game, impl):
        """选择1伤害：敌人+1伤害；致死则击败并离场。"""
        enemy = _add_enemy(game)  # health 3
        _emit(game, GameEvent.ENEMY_ATTACKS,
              investigator_id="daniela", enemy_id="enemy_1")
        assert impl.resolve_reaction(game.state, "daniela", "damage") is True
        assert enemy.damage == 1
        assert game.state.scenario.vars.get("pending_choice") is None

        # 再打2点致死 → 击败离场
        enemy.damage = 2
        _add_enemy(game, "enemy_2")
        _emit(game, GameEvent.ENEMY_ATTACKS,
              investigator_id="daniela", enemy_id="enemy_2")
        # 队列里轮到 enemy_2
        game.state.get_card_data("test_enemy").enemy_health = 3
        e2 = game.state.get_card_instance("enemy_2")
        e2.damage = 2
        assert impl.resolve_reaction(game.state, "daniela", "damage") is True
        assert "enemy_2" not in game.state.cards_in_play
        assert "enemy_2" not in game.state.get_investigator("daniela").threat_area

    def test_resolve_evade(self, game, impl):
        """选择自动躲避：敌人横置、脱离交战、留在丹妮拉所在地点。"""
        enemy = _add_enemy(game)
        loc = game.state.locations["test_location"]
        _emit(game, GameEvent.ENEMY_ATTACKS,
              investigator_id="daniela", enemy_id="enemy_1")
        assert impl.resolve_reaction(game.state, "daniela", "evade") is True
        assert enemy.exhausted
        assert "enemy_1" not in game.state.get_investigator("daniela").threat_area
        assert "enemy_1" in loc.enemies

    def test_decline(self, game, impl):
        """选择不触发：队列弹出，无效果。"""
        enemy = _add_enemy(game)
        _emit(game, GameEvent.ENEMY_ATTACKS,
              investigator_id="daniela", enemy_id="enemy_1")
        assert impl.resolve_reaction(game.state, "daniela", "decline") is True
        assert enemy.damage == 0
        assert not enemy.exhausted

    def test_multiple_attacks_queue(self, game, impl):
        """多名敌人连续攻击：按顺序逐个抉择。"""
        _add_enemy(game, "enemy_1")
        _add_enemy(game, "enemy_2")
        _emit(game, GameEvent.ENEMY_ATTACKS,
              investigator_id="daniela", enemy_id="enemy_1")
        _emit(game, GameEvent.ENEMY_ATTACKS,
              investigator_id="daniela", enemy_id="enemy_2")

        pending = game.state.scenario.vars.get("pending_choice")
        assert pending["enemy_id"] == "enemy_1"
        impl.resolve_reaction(game.state, "daniela", "damage")
        pending = game.state.scenario.vars.get("pending_choice")
        assert pending is not None and pending["enemy_id"] == "enemy_2"
        impl.resolve_reaction(game.state, "daniela", "damage")
        assert game.state.scenario.vars.get("pending_choice") is None
        assert game.state.get_card_instance("enemy_1").damage == 1
        assert game.state.get_card_instance("enemy_2").damage == 1

    def test_other_investigator_attacked_not_triggered(self, game, impl):
        """敌人攻击其他调查员不触发。"""
        other_data = make_investigator_data(id="other_inv", name="Other")
        game.register_card_data(other_data)
        game.add_investigator("other", other_data, deck=[],
                              starting_location="test_location")
        _add_enemy(game, "enemy_1", engaged=False)
        game.state.get_investigator("other").threat_area.append("enemy_1")
        _emit(game, GameEvent.ENEMY_ATTACKS,
              investigator_id="other", enemy_id="enemy_1")
        assert game.state.scenario.vars.get("pending_choice") is None


class TestDanielaElderSign:
    def test_elder_sign_plus_one_not_attacked(self, game, impl):
        """本轮未被攻击：远古印记 +1，无自动成功。"""
        ctx = _emit(
            game, GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="daniela", chaos_token=ChaosTokenType.ELDER_SIGN,
        )
        assert ctx.amount == 1
        ctx2 = _emit(
            game, GameEvent.SKILL_VALUE_DETERMINED,
            investigator_id="daniela", amount=3,
        )
        assert ctx2.amount == 3
        _emit(game, GameEvent.SKILL_TEST_ENDS, investigator_id="daniela")

    def test_elder_sign_auto_success_after_attack(self, game, impl):
        """本轮被攻击过：改为自动成功（+999 近似），不加 +1。"""
        _add_enemy(game)
        _emit(game, GameEvent.ENEMY_ATTACKS,
              investigator_id="daniela", enemy_id="enemy_1")

        ctx = _emit(
            game, GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="daniela", chaos_token=ChaosTokenType.ELDER_SIGN,
        )
        assert ctx.amount == 0  # "instead"：没有 +1
        ctx2 = _emit(
            game, GameEvent.SKILL_VALUE_DETERMINED,
            investigator_id="daniela", amount=3,
        )
        assert ctx2.amount == 3 + 999
        _emit(game, GameEvent.SKILL_TEST_ENDS, investigator_id="daniela")

        # 检定结束后标记清除：下次检定不再自动成功
        ctx3 = _emit(
            game, GameEvent.SKILL_VALUE_DETERMINED,
            investigator_id="daniela", amount=3,
        )
        assert ctx3.amount == 3

    def test_attacked_flag_resets_each_round(self, game, impl):
        """被攻击记录每轮重置。"""
        _add_enemy(game)
        _emit(game, GameEvent.ENEMY_ATTACKS,
              investigator_id="daniela", enemy_id="enemy_1")
        _emit(game, GameEvent.ROUND_BEGINS)
        ctx = _emit(
            game, GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="daniela", chaos_token=ChaosTokenType.ELDER_SIGN,
        )
        assert ctx.amount == 1  # 回到 +1
        _emit(game, GameEvent.SKILL_TEST_ENDS, investigator_id="daniela")
