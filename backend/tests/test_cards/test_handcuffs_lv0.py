"""Tests for Handcuffs (Level 0). (04265)

[行动]用战斗躲避类人生物敌人，成功后叠加手铐；
被叠加的非精英敌人不能就绪。
"""

import pytest
from backend.cards.guardian.handcuffs_lv0 import Handcuffs
from backend.engine.game import Game
from backend.models.enums import ChaosTokenType, PlayerClass
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_asset_data, make_enemy_data, make_investigator_data,
    make_location_data,
)


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)
    inv_data = make_investigator_data(combat=4, agility=1)
    g.register_card_data(inv_data)
    g.register_card_data(make_location_data())
    g.register_card_data(make_asset_data(
        id="handcuffs_lv0", name="Handcuffs", cost=2,
        card_class=PlayerClass.GUARDIAN, traits=["item", "police"],
    ))
    g.register_card_data(make_enemy_data(
        id="cultist", name="Cultist", fight=2, health=2, evade=3,
    ))
    # make_enemy_data 不支持 traits；直接补
    g.state.card_database["cultist"].traits = ["humanoid"]
    g.register_card_data(make_enemy_data(
        id="monster", name="Monster", fight=2, health=2, evade=3))
    g.state.card_database["monster"].traits = ["monster"]

    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", g.state.get_card_data("test_location"), clues=0)
    g.card_registry.register_class(Handcuffs)

    inv = g.state.get_investigator("inv1")
    inst = CardInstance(
        instance_id="cuffs_1", card_id="handcuffs_lv0",
        owner_id="inv1", controller_id="inv1",
    )
    g.state.cards_in_play["cuffs_1"] = inst
    inv.play_area.append("cuffs_1")
    impl = g.card_registry.activate_card("handcuffs_lv0", "cuffs_1", g.event_bus)
    return g, impl


def _spawn(game, card_id, instance_id):
    game.state.cards_in_play[instance_id] = CardInstance(
        instance_id=instance_id, card_id=card_id,
        owner_id="scenario", controller_id="scenario",
    )
    game.state.get_investigator("inv1").threat_area.append(instance_id)
    return game.state.cards_in_play[instance_id]


class TestHandcuffs:
    def test_evade_with_combat_and_attach(self, game):
        """用战斗代替敏捷躲避类人生物；成功后横置敌人并叠加。"""
        g, impl = game
        enemy = _spawn(g, "cultist", "enemy_1")
        g.chaos_bag.tokens = [ChaosTokenType.ZERO]
        # 战斗4+0=4 vs 躲避3 → 成功（若用敏捷1则失败）

        assert impl.activate_evade(g, "inv1", enemy_instance_id="enemy_1") is True
        assert enemy.exhausted is True
        inv = g.state.get_investigator("inv1")
        assert "enemy_1" not in inv.threat_area  # 脱离交战
        loc = g.state.get_location("test_location")
        assert "enemy_1" in loc.enemies
        # 叠加记录
        assert g.state.scenario.vars["handcuffs_attached"]["cuffs_1"] == "enemy_1"

    def test_rejects_non_humanoid(self, game):
        """非类人生物敌人：无法使用。"""
        g, impl = game
        _spawn(g, "monster", "enemy_2")
        g.chaos_bag.tokens = [ChaosTokenType.ZERO]
        assert impl.activate_evade(g, "inv1", enemy_instance_id="enemy_2") is False

    def test_attached_enemy_cannot_ready(self, game):
        """被叠加的非精英敌人在整备阶段保持横置。"""
        g, impl = game
        enemy = _spawn(g, "cultist", "enemy_1")
        g.chaos_bag.tokens = [ChaosTokenType.ZERO]
        impl.activate_evade(g, "inv1", enemy_instance_id="enemy_1")
        assert enemy.exhausted is True

        g.upkeep_phase._ready_all()
        assert enemy.exhausted is True  # 手铐阻止就绪

    def test_second_use_blocked_while_attached(self, game):
        """已叠加时不能再次使用躲避能力。"""
        g, impl = game
        _spawn(g, "cultist", "enemy_1")
        _spawn(g, "cultist", "enemy_2")
        g.chaos_bag.tokens = [ChaosTokenType.ZERO]
        impl.activate_evade(g, "inv1", enemy_instance_id="enemy_1")
        assert impl.activate_evade(g, "inv1", enemy_instance_id="enemy_2") is False
