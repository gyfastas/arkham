"""Tests for Guard Dog (Level 0)."""

import pytest
from backend.cards.guardian.guard_dog_lv0 import GuardDog
from backend.engine.event_bus import EventContext
from backend.models.enums import GameEvent, SlotType
from backend.models.state import CardInstance
from backend.tests.conftest import make_asset_data, make_enemy_data


@pytest.fixture
def dog_game(game):
    game.register_card_data(make_enemy_data())
    game.register_card_data(make_asset_data(
        id="guard_dog_lv0", name="Guard Dog",
        slots=[SlotType.ALLY], traits=["ally", "creature"],
        health=3, sanity=1,
    ))
    inv = game.state.get_investigator("test_investigator")

    dog = CardInstance(
        instance_id="dog_1", card_id="guard_dog_lv0",
        owner_id="test_investigator", controller_id="test_investigator",
    )
    game.state.cards_in_play["dog_1"] = dog
    inv.play_area.append("dog_1")

    enemy = CardInstance(
        instance_id="e1", card_id="test_enemy",
        owner_id="scenario", controller_id="scenario",
    )
    game.state.cards_in_play["e1"] = enemy
    inv.threat_area.append("e1")

    impl = GuardDog("dog_1")
    impl.register(game.event_bus, "dog_1")
    return game


def _enemy_attacks(game, inv_id="test_investigator", enemy_id="e1"):
    ctx = EventContext(
        game_state=game.state, event=GameEvent.ENEMY_ATTACKS,
        investigator_id=inv_id, enemy_id=enemy_id, source=enemy_id,
    )
    game.event_bus.emit(ctx)
    return ctx


class TestGuardDog:
    def test_card_id(self):
        assert GuardDog.card_id == "guard_dog_lv0"

    def test_retaliates_when_dog_takes_attack_damage(self, dog_game):
        """敌人攻击的伤害分给看门狗后：反击攻击者1点伤害。"""
        game = dog_game
        enemy = game.state.get_card_instance("e1")

        _enemy_attacks(game)
        game.damage_engine.deal_damage(
            "test_investigator", damage=2, source="e1",
            damage_assignment={"dog_1": 1},
        )
        assert enemy.damage == 1
        dog = game.state.get_card_instance("dog_1")
        assert dog.damage == 1

    def test_no_retaliate_when_damage_all_to_investigator(self, dog_game):
        """伤害全部给调查员（没分给狗）时不反击。"""
        game = dog_game
        enemy = game.state.get_card_instance("e1")

        _enemy_attacks(game)
        game.damage_engine.deal_damage(
            "test_investigator", damage=2, source="e1",
        )
        assert enemy.damage == 0

    def test_no_retaliate_without_attack(self, dog_game):
        """非敌人攻击的伤害（如诡计）不反击。"""
        game = dog_game
        enemy = game.state.get_card_instance("e1")

        # 没有 ENEMY_ATTACKS 快照，直接造成伤害
        game.damage_engine.deal_damage(
            "test_investigator", damage=1, source="e1",
            damage_assignment={"dog_1": 1},
        )
        assert enemy.damage == 0

    def test_no_retaliate_when_dog_not_in_play(self, game):
        """看门狗不在场时不反击。"""
        game.register_card_data(make_enemy_data())
        enemy = CardInstance(
            instance_id="e1", card_id="test_enemy",
            owner_id="scenario", controller_id="scenario",
        )
        game.state.cards_in_play["e1"] = enemy

        impl = GuardDog("dog_1")
        impl.register(game.event_bus, "dog_1")

        _enemy_attacks(game)
        game.damage_engine.deal_damage("test_investigator", damage=1, source="e1")
        assert enemy.damage == 0
