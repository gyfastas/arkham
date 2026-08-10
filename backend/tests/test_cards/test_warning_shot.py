"""Tests for Warning Shot (Level 0). (05229)

额外费用：花费你控制的一张枪械的1弹药。移动你所在地点所有非精英敌人到
一个连接地点。此行动不引起趁乱攻击。
"""

import pytest
from backend.cards.guardian.warning_shot_lv0 import WarningShot
from backend.engine.game import Game
from backend.models.enums import Action, PlayerClass, SlotType
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_asset_data, make_enemy_data, make_event_data,
    make_investigator_data, make_location_data,
)


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)

    inv_data = make_investigator_data()
    g.register_card_data(inv_data)
    g.register_card_data(make_location_data(
        id="loc_a", name="Hall", connections=["loc_b"]))
    g.register_card_data(make_location_data(
        id="loc_b", name="Cellar", connections=["loc_a"]))
    g.register_card_data(make_event_data(
        id="warning_shot_lv0", name="Warning Shot", cost=2,
        card_class=PlayerClass.GUARDIAN,
    ))
    g.register_card_data(make_asset_data(
        id="45_automatic_lv0", name=".45 Automatic", cost=4,
        slots=[SlotType.HAND], traits=["item", "weapon", "firearm"],
        uses={"ammo": 4},
    ))
    g.register_card_data(make_enemy_data(
        id="ghoul", name="Ghoul", fight=3, health=3, damage=1, horror=1,
    ))
    g.register_card_data(make_enemy_data(
        id="priest", name="Priest of Two Faiths", fight=4, health=4,
        damage=2, horror=2, keywords=["elite"],
    ))

    g.add_investigator("inv1", inv_data, starting_location="loc_a")
    g.add_location("loc_a", g.state.get_card_data("loc_a"))
    g.add_location("loc_b", g.state.get_card_data("loc_b"))
    g.card_registry.register_class(WarningShot)

    inv = g.state.get_investigator("inv1")
    inv.hand.append("warning_shot_lv0")
    inv.actions_remaining = 3
    inv.resources = 5
    return g


def _deploy_gun(game, ammo=1):
    game.state.cards_in_play["gun_1"] = CardInstance(
        instance_id="gun_1", card_id="45_automatic_lv0",
        owner_id="inv1", controller_id="inv1", uses={"ammo": ammo},
    )
    game.state.get_investigator("inv1").play_area.append("gun_1")
    return game.state.cards_in_play["gun_1"]


def _spawn(game, instance_id, card_id, *, engaged=False):
    game.state.cards_in_play[instance_id] = CardInstance(
        instance_id=instance_id, card_id=card_id,
        owner_id="scenario", controller_id="scenario",
    )
    if engaged:
        game.state.get_investigator("inv1").threat_area.append(instance_id)
    else:
        game.state.get_location("loc_a").enemies.append(instance_id)
    return game.state.cards_in_play[instance_id]


class TestWarningShot:
    def test_moves_non_elite_and_spends_ammo(self, game):
        """花1弹药：地点上+交战中的非精英敌人都移到连接地点，精英不动。"""
        gun = _deploy_gun(game, ammo=2)
        _spawn(game, "e_ghoul", "ghoul")                    # 地点上非精英
        _spawn(game, "e_rat", "ghoul", engaged=True)        # 交战非精英
        _spawn(game, "e_elite", "priest")                   # 地点上精英

        ok = game.action_resolver.perform_action(
            "inv1", Action.PLAY, card_id="warning_shot_lv0",
        )
        assert ok is True
        assert gun.uses["ammo"] == 1  # 额外费用已花

        loc_a = game.state.get_location("loc_a")
        loc_b = game.state.get_location("loc_b")
        inv = game.state.get_investigator("inv1")
        assert "e_ghoul" in loc_b.enemies and "e_ghoul" not in loc_a.enemies
        assert "e_rat" in loc_b.enemies
        assert "e_rat" not in inv.threat_area  # 交战被解除
        assert "e_elite" in loc_a.enemies  # 精英不动

    def test_no_attack_of_opportunity(self, game):
        """此行动不引起趁乱攻击：交战精英待命，打出后调查员无伤。"""
        _deploy_gun(game)
        _spawn(game, "e_elite", "priest", engaged=True)  # 交战精英（精英不动）

        game.action_resolver.perform_action(
            "inv1", Action.PLAY, card_id="warning_shot_lv0",
        )
        inv = game.state.get_investigator("inv1")
        # 精英仍在交战且待命；若 AoO 未豁免会受到 2伤害2恐惧
        assert "e_elite" in inv.threat_area
        assert inv.damage == 0 and inv.horror == 0

    def test_no_firearm_ammo_fizzles(self, game):
        """没有可用弹药：额外费用付不出，敌人不移动。"""
        _deploy_gun(game, ammo=0)
        _spawn(game, "e_ghoul", "ghoul")

        game.action_resolver.perform_action(
            "inv1", Action.PLAY, card_id="warning_shot_lv0",
        )
        loc_a = game.state.get_location("loc_a")
        loc_b = game.state.get_location("loc_b")
        assert "e_ghoul" in loc_a.enemies
        assert "e_ghoul" not in loc_b.enemies
