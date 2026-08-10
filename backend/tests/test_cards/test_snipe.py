"""Tests for Snipe (Level 1). (08087)

本回合下一个用远程/枪械支援的攻击：skull/cultist/tablet/elder_thing/auto_fail
视为0（auto_fail 取消自动失败）。
"""

import pytest

from backend.cards.guardian.snipe_lv1 import Snipe
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import (
    Action, CardType, ChaosTokenType, GameEvent, PlayerClass, SlotType,
)
from backend.models.state import CardData, CardInstance
from backend.tests.conftest import (
    make_enemy_data, make_event_data, make_investigator_data,
    make_location_data,
)


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)

    inv_data = make_investigator_data(combat=4)
    g.register_card_data(inv_data)
    loc = make_location_data()
    g.register_card_data(loc)
    g.register_card_data(make_event_data(
        id="snipe_lv1", name="Snipe", cost=0,
        card_class=PlayerClass.GUARDIAN,
    ))
    g.register_card_data(make_enemy_data(id="ghoul", fight=3, health=3))
    g.register_card_data(CardData(
        id="rifle", name="Rifle", name_cn="步枪", type=CardType.ASSET,
        card_class=PlayerClass.GUARDIAN, cost=3, slots=[SlotType.HAND],
        traits=["item", "weapon", "firearm", "ranged"],
    ))

    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", g.state.get_card_data("test_location"))
    g.card_registry.register_class(Snipe)

    gun = CardInstance(
        instance_id="gun_1", card_id="rifle",
        owner_id="inv1", controller_id="inv1", slot_used=[SlotType.HAND],
    )
    g.state.cards_in_play["gun_1"] = gun
    g.state.get_investigator("inv1").play_area.append("gun_1")

    enemy = CardInstance(
        instance_id="enemy_1", card_id="ghoul",
        owner_id="scenario", controller_id="scenario",
    )
    g.state.cards_in_play["enemy_1"] = enemy
    g.state.get_investigator("inv1").threat_area.append("enemy_1")

    inv = g.state.get_investigator("inv1")
    inv.hand.append("snipe_lv1")
    inv.actions_remaining = 3
    return g


class TestSnipe:
    def test_auto_fail_treated_as_zero(self, game):
        """袋中仅 auto_fail：狙击后视为0，战斗4 vs 3 成功并造成1伤害。"""
        game.chaos_bag.tokens = [ChaosTokenType.AUTO_FAIL]

        game.action_resolver.perform_action(
            "inv1", Action.PLAY, card_id="snipe_lv1",
        )
        game.action_resolver.perform_action(
            "inv1", Action.FIGHT, enemy_instance_id="enemy_1",
            weapon_instance_id="gun_1",
        )
        enemy = game.state.get_card_instance("enemy_1")
        assert enemy.damage == 1

    def test_symbol_token_modifier_zeroed(self, game):
        """skull 等标记的修正值被归零（经 CHAOS_TOKEN_RESOLVED）。"""
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]
        game.action_resolver.perform_action(
            "inv1", Action.PLAY, card_id="snipe_lv1",
        )
        # 武装后先发起一次匹配的攻击（FIGHT_ACTION_INITIATED 标记消耗）
        ctx = EventContext(
            game_state=game.state, event=GameEvent.FIGHT_ACTION_INITIATED,
            investigator_id="inv1", enemy_id="enemy_1", source="gun_1",
        )
        game.event_bus.emit(ctx)
        token_ctx = EventContext(
            game_state=game.state, event=GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="inv1", chaos_token=ChaosTokenType.SKULL,
            amount=-3,
        )
        game.event_bus.emit(token_ctx)
        assert token_ctx.amount == 0

    def test_non_firearm_attack_not_consumed(self, game):
        """徒手攻击（无武器来源）不消耗狙击武装。"""
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]
        game.action_resolver.perform_action(
            "inv1", Action.PLAY, card_id="snipe_lv1",
        )
        ctx = EventContext(
            game_state=game.state, event=GameEvent.FIGHT_ACTION_INITIATED,
            investigator_id="inv1", enemy_id="enemy_1", source=None,
        )
        game.event_bus.emit(ctx)
        # 武装未消耗：随后的 skull 不会被归零窗口捕获（active 未置位）
        token_ctx = EventContext(
            game_state=game.state, event=GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="inv1", chaos_token=ChaosTokenType.SKULL,
            amount=-3,
        )
        game.event_bus.emit(token_ctx)
        assert token_ctx.amount == -3
