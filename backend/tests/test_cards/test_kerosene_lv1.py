"""Tests for Kerosene (Level 1). (04304)

[行动]本轮有敌人在此地点被击败时，横置+1补给：同地点治愈至多2点恐惧。
"""

import pytest
from backend.cards.guardian.kerosene_lv1 import Kerosene
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import GameEvent, PlayerClass
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_asset_data, make_enemy_data, make_investigator_data,
    make_location_data,
)


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)
    inv_data = make_investigator_data()
    g.register_card_data(inv_data)
    g.register_card_data(make_location_data())
    g.register_card_data(make_asset_data(
        id="kerosene_lv1", name="Kerosene", cost=3,
        card_class=PlayerClass.GUARDIAN, traits=["item"], uses={"suppliess": 3},
    ))
    g.register_card_data(make_enemy_data(fight=3, health=1))

    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", g.state.get_card_data("test_location"), clues=0)
    g.card_registry.register_class(Kerosene)

    inv = g.state.get_investigator("inv1")
    inst = CardInstance(
        instance_id="kerosene_1", card_id="kerosene_lv1",
        owner_id="inv1", controller_id="inv1", uses={"suppliess": 3},
    )
    g.state.cards_in_play["kerosene_1"] = inst
    inv.play_area.append("kerosene_1")
    impl = g.card_registry.activate_card("kerosene_lv1", "kerosene_1", g.event_bus)
    return g, impl


def _defeat_enemy_here(game):
    game.state.cards_in_play["enemy_1"] = CardInstance(
        instance_id="enemy_1", card_id="test_enemy",
        owner_id="scenario", controller_id="scenario",
    )
    game.state.get_investigator("inv1").threat_area.append("enemy_1")
    game.damage_engine.deal_damage_to_enemy("enemy_1", 1, investigator_id="inv1")


class TestKerosene:
    def test_heal_2_horror_after_local_defeat(self, game):
        """本轮此地有敌人被击败：横置+1补给治愈2恐惧。"""
        g, impl = game
        inv = g.state.get_investigator("inv1")
        inv.horror = 3
        _defeat_enemy_here(g)

        assert impl.activate(g.state, "inv1") is True
        assert inv.horror == 1  # 治愈2
        inst = g.state.get_card_instance("kerosene_1")
        assert inst.exhausted is True
        assert inst.uses["suppliess"] == 2

    def test_requires_defeat_this_round(self, game):
        """本轮此地没有敌人被击败：不可用。"""
        g, impl = game
        inv = g.state.get_investigator("inv1")
        inv.horror = 2
        assert impl.activate(g.state, "inv1") is False
        assert inv.horror == 2

    def test_defeat_tracking_resets_each_round(self, game):
        """跨轮后击败记录清空。"""
        g, impl = game
        inv = g.state.get_investigator("inv1")
        inv.horror = 2
        _defeat_enemy_here(g)
        g.event_bus.emit(EventContext(
            game_state=g.state, event=GameEvent.ROUND_BEGINS,
        ))
        assert impl.activate(g.state, "inv1") is False

    def test_discards_when_out_of_supplies(self, game):
        """补给耗尽：弃置。"""
        g, impl = game
        inv = g.state.get_investigator("inv1")
        inv.horror = 2
        g.state.get_card_instance("kerosene_1").uses["suppliess"] = 1
        _defeat_enemy_here(g)

        assert impl.activate(g.state, "inv1") is True
        assert "kerosene_1" not in inv.play_area
        assert "kerosene_lv1" in inv.discard
