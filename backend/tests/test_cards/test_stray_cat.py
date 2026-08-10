"""Tests for Stray Cat (Level 0)."""

import pytest
from backend.cards.survivor.stray_cat_lv0 import StrayCat
from backend.models.enums import PlayerClass, SlotType
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_enemy_data, make_investigator_data, make_asset_data, make_location_data,
)
from backend.engine.game import Game


@pytest.fixture
def game():
    g = Game("test")
    inv_data = make_investigator_data()
    g.register_card_data(inv_data)
    loc = make_location_data()
    g.register_card_data(loc)
    loc_b = make_location_data(id="loc_b")
    g.register_card_data(loc_b)

    cat_data = make_asset_data(
        id="stray_cat_lv0", name="Stray Cat", cost=1,
        card_class=PlayerClass.SURVIVOR,
        slots=[SlotType.ALLY], health=1,
        traits=["ally", "creature"],
    )
    g.register_card_data(cat_data)
    g.register_card_data(make_enemy_data(id="test_enemy"))
    g.register_card_data(make_enemy_data(id="elite_enemy", keywords=["elite"]))
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)
    g.add_location("loc_b", loc_b, clues=0)
    g.card_registry.register_class(StrayCat)
    return g


def _put_cat_in_play(game):
    inv = game.state.get_investigator("inv1")
    iid = game.state.next_instance_id()
    game.state.cards_in_play[iid] = CardInstance(
        instance_id=iid, card_id="stray_cat_lv0",
        owner_id="inv1", controller_id="inv1", slot_used=[SlotType.ALLY],
    )
    inv.play_area.append(iid)
    impl = StrayCat(iid)
    impl.register(game.event_bus, iid)
    return impl


def _spawn_enemy(game, instance_id, card_id="test_enemy", where="location"):
    game.state.cards_in_play[instance_id] = CardInstance(
        instance_id=instance_id, card_id=card_id,
        owner_id="scenario", controller_id="scenario",
    )
    if where == "engaged":
        game.state.get_investigator("inv1").threat_area.append(instance_id)
    elif where == "location":
        game.state.get_location("test_location").enemies.append(instance_id)
    else:  # 其他地点
        game.state.get_location("loc_b").enemies.append(instance_id)


class TestStrayCat:
    def test_card_registered(self, game):
        assert "stray_cat_lv0" in game.card_registry.registered_cards

    def test_has_health(self, game):
        cat_data = game.state.card_database["stray_cat_lv0"]
        assert cat_data.health == 1

    def test_evades_unengaged_enemy_at_location(self, game):
        """官方：你所在地点的非精英敌人（不要求与你交战）。"""
        impl = _put_cat_in_play(game)
        _spawn_enemy(game, "enemy_1", where="location")
        inv = game.state.get_investigator("inv1")

        assert impl.activate(game.state, "inv1", "enemy_1") is True

        loc = game.state.get_location("test_location")
        enemy = game.state.get_card_instance("enemy_1")
        assert enemy.exhausted is True
        assert "enemy_1" in loc.enemies
        assert impl.instance_id not in inv.play_area
        assert "stray_cat_lv0" in inv.discard

    def test_evades_engaged_enemy(self, game):
        impl = _put_cat_in_play(game)
        _spawn_enemy(game, "enemy_1", where="engaged")
        inv = game.state.get_investigator("inv1")

        assert impl.activate(game.state, "inv1", "enemy_1") is True
        assert "enemy_1" not in inv.threat_area
        assert game.state.get_card_instance("enemy_1").exhausted is True

    def test_rejects_elite(self, game):
        impl = _put_cat_in_play(game)
        _spawn_enemy(game, "enemy_1", card_id="elite_enemy", where="location")
        inv = game.state.get_investigator("inv1")

        assert impl.activate(game.state, "inv1", "enemy_1") is False
        assert impl.instance_id in inv.play_area

    def test_rejects_enemy_elsewhere(self, game):
        impl = _put_cat_in_play(game)
        _spawn_enemy(game, "enemy_1", where="elsewhere")
        inv = game.state.get_investigator("inv1")

        assert impl.activate(game.state, "inv1", "enemy_1") is False
        assert impl.instance_id in inv.play_area
