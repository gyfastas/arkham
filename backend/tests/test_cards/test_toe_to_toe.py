"""Tests for Toe to Toe (Level 0). (08020)

攻击：+1伤害并自动成功；额外费用是所选敌人攻击你；Fight 行动不引起趁乱攻击。
"""

import pytest
from backend.cards.guardian.toe_to_toe_lv0 import ToeToToe
from backend.engine.game import Game
from backend.models.enums import Action, PlayerClass
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_enemy_data, make_event_data, make_investigator_data,
    make_location_data,
)


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)

    inv_data = make_investigator_data()
    g.register_card_data(inv_data)
    g.register_card_data(make_location_data())
    g.register_card_data(make_event_data(
        id="toe_to_toe_lv0", name="Toe to Toe", cost=0,
        card_class=PlayerClass.GUARDIAN,
    ))
    g.register_card_data(make_enemy_data(
        id="ghoul", name="Ghoul", fight=3, health=3, damage=1, horror=1,
    ))

    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", g.state.get_card_data("test_location"))
    g.card_registry.register_class(ToeToToe)

    inv = g.state.get_investigator("inv1")
    inv.hand.append("toe_to_toe_lv0")
    inv.actions_remaining = 3
    return g


def _spawn_engaged(game, instance_id="enemy_1"):
    game.state.cards_in_play[instance_id] = CardInstance(
        instance_id=instance_id, card_id="ghoul",
        owner_id="scenario", controller_id="scenario",
    )
    game.state.get_investigator("inv1").threat_area.append(instance_id)
    return game.state.cards_in_play[instance_id]


class TestToeToe:
    def test_auto_success_plus1_damage_and_enemy_attacks(self, game):
        """打出：敌人先攻击你（1伤害1恐惧），随后攻击自动成功造成2伤害。"""
        enemy = _spawn_engaged(game)

        ok = game.action_resolver.perform_action(
            "inv1", Action.PLAY, card_id="toe_to_toe_lv0",
        )
        assert ok is True
        inv = game.state.get_investigator("inv1")
        assert inv.damage == 1 and inv.horror == 1  # 额外费用：敌人攻击
        assert enemy.damage == 2  # 基础1 + 1
        assert "toe_to_toe_lv0" in inv.discard

    def test_no_attack_of_opportunity(self, game):
        """Fight 行动：打出不引起趁乱攻击（敌人只攻击一次，即额外费用）。"""
        _spawn_engaged(game)
        game.action_resolver.perform_action(
            "inv1", Action.PLAY, card_id="toe_to_toe_lv0",
        )
        inv = game.state.get_investigator("inv1")
        # 若 AoO 未被豁免，准备好的交战敌人会再攻击一次（共2伤害2恐惧）
        assert inv.damage == 1 and inv.horror == 1

    def test_can_defeat_enemy(self, game):
        """2伤害足以击败2血敌人：敌人离场入遭遇弃牌堆。"""
        _spawn_engaged(game)
        game.state.get_card_data("ghoul").enemy_health = 2

        game.action_resolver.perform_action(
            "inv1", Action.PLAY, card_id="toe_to_toe_lv0",
        )
        inv = game.state.get_investigator("inv1")
        assert game.state.get_card_instance("enemy_1") is None
        assert "enemy_1" not in inv.threat_area
        assert "ghoul" in game.state.scenario.encounter_discard

    def test_no_enemy_fizzles(self, game):
        """所在地点没有敌人：效果不结算（无人受伤）。"""
        ok = game.action_resolver.perform_action(
            "inv1", Action.PLAY, card_id="toe_to_toe_lv0",
        )
        assert ok is True  # 打出流程已完成
        inv = game.state.get_investigator("inv1")
        assert inv.damage == 0 and inv.horror == 0

    def test_explicit_target_at_location(self, game):
        """显式指定地点上未交战的敌人为目标（引擎 PLAY 不透传目标，
        会话层可经 ctx.extra["enemy_instance_id"] 指定）。"""
        from backend.engine.event_bus import EventContext
        from backend.models.enums import GameEvent

        impl = ToeToToe("impl_manual")
        impl.register(game.event_bus, "impl_manual")

        loc = game.state.get_location("test_location")
        game.state.cards_in_play["enemy_2"] = CardInstance(
            instance_id="enemy_2", card_id="ghoul",
            owner_id="scenario", controller_id="scenario",
        )
        loc.enemies.append("enemy_2")

        ctx = EventContext(
            game_state=game.state, event=GameEvent.CARD_PLAYED,
            investigator_id="inv1",
            extra={"card_id": "toe_to_toe_lv0",
                   "enemy_instance_id": "enemy_2"},
        )
        game.event_bus.emit(ctx)

        enemy = game.state.get_card_instance("enemy_2")
        inv = game.state.get_investigator("inv1")
        assert enemy.damage == 2
        assert inv.damage == 1 and inv.horror == 1
