"""Tests for Venturer (Level 0). (04018)

使用(3补给)。[快速]花费1补给并横置冒险家：在你所在地点一位调查员控制的
一张支援上放置1补给或弹药。
"""

import pytest
from backend.cards.guardian.venturer_lv0 import Venturer
from backend.engine.game import Game
from backend.models.enums import PlayerClass, SlotType
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_asset_data, make_investigator_data, make_location_data,
)


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)

    inv_data = make_investigator_data()
    g.register_card_data(inv_data)
    g.register_card_data(make_location_data())
    g.register_card_data(make_asset_data(
        id="venturer_lv0", name="Venturer", cost=4,
        card_class=PlayerClass.GUARDIAN,
        slots=[SlotType.ALLY], health=2, sanity=2,
        traits=["ally", "wayfarer"], uses={"supplies": 3},
    ))
    g.register_card_data(make_asset_data(
        id="45_automatic_lv0", name=".45 Automatic", cost=4,
        slots=[SlotType.HAND], traits=["item", "weapon", "firearm"],
        uses={"ammo": 4},
    ))
    g.register_card_data(make_asset_data(
        id="first_aid_lv0", name="First Aid", cost=2,
        traits=["item"], uses={"supplies": 3},
    ))
    g.register_card_data(make_asset_data(
        id="machete_lv0", name="Machete", cost=3,
        slots=[SlotType.HAND], traits=["item", "weapon", "melee"],
    ))

    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", g.state.get_card_data("test_location"))
    g.card_registry.register_class(Venturer)
    return g


def _deploy(game, card_id, instance_id, uses=None):
    game.state.cards_in_play[instance_id] = CardInstance(
        instance_id=instance_id, card_id=card_id,
        owner_id="inv1", controller_id="inv1",
        uses=dict(uses or {}),
    )
    game.state.get_investigator("inv1").play_area.append(instance_id)
    return game.state.cards_in_play[instance_id]


def _deploy_venturer(game):
    inst = _deploy(game, "venturer_lv0", "venturer_1", uses={"supplies": 3})
    game.card_registry.activate_card("venturer_lv0", "venturer_1",
                                     game.event_bus)
    impl = game.card_registry.active_instances["venturer_1"]
    return inst, impl


class TestVenturer:
    def test_place_ammo_on_firearm(self, game):
        """花1补给并横置：默认给同地点枪械放1弹药。"""
        venturer, impl = _deploy_venturer(game)
        gun = _deploy(game, "45_automatic_lv0", "gun_1", uses={"ammo": 1})

        ok = impl.activate(game.state, "inv1")
        assert ok is True
        assert venturer.uses["supplies"] == 2
        assert venturer.exhausted is True
        assert gun.uses["ammo"] == 2

    def test_explicit_target_and_supplies(self, game):
        """显式指定目标与 token 类型：给急救包放1补给。"""
        venturer, impl = _deploy_venturer(game)
        aid = _deploy(game, "first_aid_lv0", "aid_1", uses={"supplies": 1})
        _deploy(game, "45_automatic_lv0", "gun_1", uses={"ammo": 1})

        ok = impl.activate(game.state, "inv1",
                           target_instance_id="aid_1", token_type="supplies")
        assert ok is True
        assert aid.uses["supplies"] == 2
        assert venturer.uses["supplies"] == 2

    def test_skips_assets_without_uses(self, game):
        """默认选择跳过没有弹药/补给用途的支援（弯刀）。"""
        _, impl = _deploy_venturer(game)
        machete = _deploy(game, "machete_lv0", "machete_1")
        gun = _deploy(game, "45_automatic_lv0", "gun_1", uses={"ammo": 0})

        ok = impl.activate(game.state, "inv1")
        assert ok is True
        assert gun.uses["ammo"] == 1
        assert machete.uses == {}

    def test_fails_when_exhausted_or_empty(self, game):
        """已横置或没有补给时不能激活。"""
        venturer, impl = _deploy_venturer(game)
        _deploy(game, "45_automatic_lv0", "gun_1", uses={"ammo": 1})

        venturer.exhausted = True
        assert impl.activate(game.state, "inv1") is False

        venturer.exhausted = False
        venturer.uses["supplies"] = 0
        assert impl.activate(game.state, "inv1") is False
