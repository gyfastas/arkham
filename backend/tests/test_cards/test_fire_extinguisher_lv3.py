"""Tests for Fire Extinguisher (Level 3)."""

import pytest

from backend.cards.survivor.fire_extinguisher_lv3 import FireExtinguisher
from backend.engine.game import Game
from backend.models.enums import Action, ChaosTokenType, SlotType
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_asset_data, make_enemy_data, make_investigator_data,
    make_location_data,
)


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)
    inv_data = make_investigator_data(combat=3)
    g.register_card_data(inv_data)
    loc = make_location_data()
    g.register_card_data(loc)
    g.register_card_data(make_asset_data(
        id="fire_extinguisher_lv3", name="Fire Extinguisher", cost=2,
        slots=[SlotType.HAND], traits=["item", "tool", "melee"]))
    g.register_card_data(make_enemy_data(fight=3, health=10, evade=2))
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)
    g.card_registry.register_class(FireExtinguisher)
    return g


def _put_into_play(game):
    inv = game.state.get_investigator("inv1")
    game.state.cards_in_play["ext_1"] = CardInstance(
        instance_id="ext_1", card_id="fire_extinguisher_lv3",
        owner_id="inv1", controller_id="inv1",
        slot_used=[SlotType.HAND],
    )
    inv.play_area.append("ext_1")
    impl = FireExtinguisher("ext_1")
    impl.register(game.event_bus, "ext_1")
    return inv, impl


def _engage(game, instance_id):
    inv = game.state.get_investigator("inv1")
    game.state.cards_in_play[instance_id] = CardInstance(
        instance_id=instance_id, card_id="test_enemy",
        owner_id="scenario", controller_id="scenario",
    )
    inv.threat_area.append(instance_id)


class TestFireExtinguisher:
    def test_card_registered(self, game):
        assert "fire_extinguisher_lv3" in \
            game.card_registry.registered_cards

    def test_fight_bonus_and_damage(self, game):
        """以本卡攻击：+1战斗、成功+1伤害。"""
        inv, _impl = _put_into_play(game)
        _engage(game, "enemy_1")
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]  # 3+1=4 vs 3 成功
        assert game.action_resolver.perform_action(
            "inv1", Action.FIGHT, enemy_instance_id="enemy_1",
            weapon_instance_id="ext_1") is True
        enemy = game.state.get_card_instance("enemy_1")
        assert enemy.damage == 2  # 1基础 + 1卡面

    def test_discard_evades_all_engaged(self, game):
        """丢弃灭火器：自动躲避所有交战敌人。"""
        inv, impl = _put_into_play(game)
        _engage(game, "enemy_1")
        _engage(game, "enemy_2")
        loc = game.state.get_location("test_location")

        assert impl.activate_evade(game.state, "inv1") is True
        assert inv.threat_area == []
        assert "ext_1" not in inv.play_area
        assert "fire_extinguisher_lv3" in inv.discard
        for eid in ("enemy_1", "enemy_2"):
            enemy = game.state.get_card_instance(eid)
            assert enemy.exhausted is True
            assert eid in loc.enemies

    def test_exile_discards_non_elite_enemies(self, game):
        """放逐灭火器：被躲避的非精英敌人被丢弃。"""
        inv, impl = _put_into_play(game)
        _engage(game, "enemy_1")
        _engage(game, "enemy_2")

        assert impl.activate_evade(game.state, "inv1", exile=True) is True
        assert "ext_1" not in inv.play_area
        assert "fire_extinguisher_lv3" in \
            game.state.scenario.vars["exiled_cards"]
        for eid in ("enemy_1", "enemy_2"):
            assert eid not in game.state.cards_in_play
        assert game.state.scenario.encounter_discard.count("test_enemy") == 2
