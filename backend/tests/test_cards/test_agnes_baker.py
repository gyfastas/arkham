"""Tests for Agnes Baker investigator ability."""

import pytest
from backend.cards.mystic.agnes_baker import AgnesBaker
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import ChaosTokenType, GameEvent
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_enemy_data, make_investigator_data, make_location_data,
)


@pytest.fixture
def game():
    g = Game("test_agnes")
    g.chaos_bag.seed(42)

    inv_data = make_investigator_data(id="agnes_baker", name="Agnes Baker")
    g.register_card_data(inv_data)

    loc_data = make_location_data()
    g.register_card_data(loc_data)

    enemy_data = make_enemy_data()
    g.register_card_data(enemy_data)

    deck = ["card_a", "card_b", "card_c", "card_d", "card_e"] * 3
    g.add_investigator("agnes", inv_data, deck=deck, starting_location="test_location")
    g.add_location("test_location", loc_data, clues=3)

    return g


@pytest.fixture
def impl(game):
    impl = AgnesBaker("test_instance")
    impl.register(game.event_bus, "test_instance")
    return impl


def _add_enemy(game, instance_id):
    enemy = CardInstance(
        instance_id=instance_id, card_id="test_enemy",
        owner_id="scenario", controller_id="scenario",
    )
    game.state.cards_in_play[instance_id] = enemy
    return enemy


def _emit(game, event, **kwargs):
    ctx = EventContext(game_state=game.state, event=event, **kwargs)
    game.event_bus.emit(ctx)
    return ctx


class TestAgnesBaker:
    def test_horror_triggers_damage_once_per_phase(self, game, impl):
        """被放置恐惧后对所在地敌人造成1伤害；每阶段限1次，阶段切换后重置。"""
        enemy = _add_enemy(game, "enemy_1")
        game.state.locations["test_location"].enemies.append("enemy_1")

        _emit(game, GameEvent.HORROR_ASSIGNED, investigator_id="agnes", amount=1)
        assert enemy.damage == 1

        # 同一阶段再次放置恐惧：不再触发
        _emit(game, GameEvent.HORROR_ASSIGNED, investigator_id="agnes", amount=2)
        assert enemy.damage == 1

        # 新阶段开始：限次重置
        _emit(game, GameEvent.ENEMY_PHASE_BEGINS)
        _emit(game, GameEvent.HORROR_ASSIGNED, investigator_id="agnes", amount=1)
        assert enemy.damage == 2

    def test_target_override_and_engaged_priority(self, game, impl):
        """可用 scenario.vars["agnes_baker_target"] 指定目标；默认取第一个候选。"""
        engaged = _add_enemy(game, "enemy_engaged")
        other = _add_enemy(game, "enemy_location")
        inv = game.state.get_investigator("agnes")
        inv.threat_area.append("enemy_engaged")
        game.state.locations["test_location"].enemies.append("enemy_location")

        # 默认优先交战中的敌人
        _emit(game, GameEvent.HORROR_ASSIGNED, investigator_id="agnes", amount=1)
        assert engaged.damage == 1
        assert other.damage == 0

        # 指定目标
        _emit(game, GameEvent.ENEMY_PHASE_BEGINS)
        game.state.scenario.vars["agnes_baker_target"] = "enemy_location"
        _emit(game, GameEvent.HORROR_ASSIGNED, investigator_id="agnes", amount=1)
        assert engaged.damage == 1
        assert other.damage == 1

    def test_no_trigger_for_other_investigators(self, game, impl):
        """其他调查员被放置恐惧时不触发。"""
        other_data = make_investigator_data(id="other_investigator", name="Other")
        game.register_card_data(other_data)
        game.add_investigator("other", other_data, deck=[], starting_location="test_location")

        enemy = _add_enemy(game, "enemy_1")
        game.state.locations["test_location"].enemies.append("enemy_1")

        _emit(game, GameEvent.HORROR_ASSIGNED, investigator_id="other", amount=1)
        assert enemy.damage == 0

    def test_no_trigger_when_horror_fully_soaked_by_ally(self, game, impl):
        """恐惧全部被盟友吸收（未放到阿格尼丝身上）时不触发。"""
        from backend.tests.conftest import make_asset_data
        ally_data = make_asset_data(
            id="ally_lv0", name="Ally", health=2, sanity=2,
        )
        game.register_card_data(ally_data)
        ally = CardInstance(
            instance_id="ally_1", card_id="ally_lv0",
            owner_id="agnes", controller_id="agnes",
        )
        game.state.cards_in_play["ally_1"] = ally
        inv = game.state.get_investigator("agnes")
        inv.play_area.append("ally_1")

        enemy = _add_enemy(game, "enemy_1")
        game.state.locations["test_location"].enemies.append("enemy_1")

        # 首次事件建立盟友快照（无吸收）
        _emit(game, GameEvent.HORROR_ASSIGNED, investigator_id="agnes", amount=0)
        # 盟友吸收1点（模拟 horror_assignment 结算后的状态）后发出事件
        ally.horror += 1
        _emit(game, GameEvent.HORROR_ASSIGNED, investigator_id="agnes", amount=1)
        assert enemy.damage == 0

        # 部分吸收：2点恐惧盟友吸收1点，1点落到阿格尼丝 → 触发
        _emit(game, GameEvent.ENEMY_PHASE_BEGINS)
        ally.horror += 1
        _emit(game, GameEvent.HORROR_ASSIGNED, investigator_id="agnes", amount=2)
        assert enemy.damage == 1

    def test_elder_sign_bonus_per_horror(self, game, impl):
        """远古印记：阿格尼丝身上每有1点恐惧 +1。"""
        inv = game.state.get_investigator("agnes")
        inv.horror = 3

        ctx = _emit(
            game, GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="agnes", chaos_token=ChaosTokenType.ELDER_SIGN,
        )
        assert ctx.amount == 3
