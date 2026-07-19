"""Tests for victory display on enemy defeat."""

from backend.engine.game import Game
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_enemy_data,
    make_investigator_data,
    make_location_data,
)


def _make_game():
    g = Game("the_gathering")
    inv_data = make_investigator_data()
    g.register_card_data(inv_data)
    loc_data = make_location_data()
    g.register_card_data(loc_data)
    g.add_investigator("player", inv_data, starting_location="test_location")
    g.add_location("test_location", loc_data)
    return g


def _add_enemy(game, instance_id, card_id, health, victory):
    cd = make_enemy_data(id=card_id, health=health)
    cd.victory = victory
    game.register_card_data(cd)
    enemy = CardInstance(
        instance_id=instance_id, card_id=card_id,
        owner_id="scenario", controller_id="scenario",
    )
    game.state.cards_in_play[instance_id] = enemy
    game.state.locations["test_location"].enemies.append(instance_id)
    return enemy


class TestVictoryDisplay:
    def test_enemy_with_victory_goes_to_display(self):
        g = _make_game()
        _add_enemy(g, "e1", "ghoul_priest", health=2, victory=2)

        g.damage_engine.deal_damage_to_enemy("e1", 2)
        assert "ghoul_priest" in g.state.scenario.victory_display
        assert "e1" not in g.state.cards_in_play

    def test_enemy_without_victory_not_in_display(self):
        g = _make_game()
        _add_enemy(g, "e1", "swarm_of_rats", health=1, victory=0)

        g.damage_engine.deal_damage_to_enemy("e1", 1)
        assert g.state.scenario.victory_display == []

    def test_victory_xp_sum(self):
        g = _make_game()
        _add_enemy(g, "e1", "ghoul_priest", health=2, victory=2)
        _add_enemy(g, "e2", "icy_ghoul", health=1, victory=1)

        g.damage_engine.deal_damage_to_enemy("e1", 2)
        g.damage_engine.deal_damage_to_enemy("e2", 1)

        total = sum(
            g.state.get_card_data(cid).victory
            for cid in g.state.scenario.victory_display
        )
        assert total == 3
