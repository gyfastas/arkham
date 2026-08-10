"""Tests for Bury Them Deep (Level 0) — William Yorick signature event."""

from backend.cards.neutral.bury_them_deep_lv0 import BuryThemDeep
from backend.models.state import CardInstance
from backend.tests.conftest import make_enemy_data


def _setup(game, elite=False, engaged=True):
    BuryThemDeep("b1").register(game.event_bus, "b1")
    inv = game.state.get_investigator("test_investigator")
    inv.hand.append("bury_them_deep_lv0")

    enemy_data = make_enemy_data(id="ghoul", health=2)
    enemy_data.traits = ["humanoid", "ghoul"] + (["elite"] if elite else [])
    game.register_card_data(enemy_data)
    enemy = CardInstance(
        instance_id="e1", card_id="ghoul",
        owner_id="scenario", controller_id="scenario",
    )
    game.state.cards_in_play["e1"] = enemy
    if engaged:
        inv.threat_area.append("e1")
    else:
        game.state.get_location("test_location").enemies.append("e1")
    return inv


class TestBuryThemDeep:
    def test_engaged_non_elite_goes_to_victory(self, game):
        """非精英敌人被击败后：敌人与本卡进入胜利牌区。"""
        inv = _setup(game)
        game.damage_engine.deal_damage_to_enemy(
            "e1", 2, investigator_id="test_investigator",
        )
        vd = game.state.scenario.victory_display
        assert "ghoul" in vd
        assert "bury_them_deep_lv0" in vd
        assert "bury_them_deep_lv0" not in inv.hand

    def test_unengaged_at_location_also_works(self, game):
        """在你所在地点未交战的敌人也算"你所在地点"。"""
        _setup(game, engaged=False)
        game.damage_engine.deal_damage_to_enemy(
            "e1", 2, investigator_id="test_investigator",
        )
        assert "ghoul" in game.state.scenario.victory_display

    def test_elite_enemy_not_buried(self, game):
        """精英敌人不触发。"""
        inv = _setup(game, elite=True)
        game.damage_engine.deal_damage_to_enemy(
            "e1", 2, investigator_id="test_investigator",
        )
        assert game.state.scenario.victory_display == []
        assert "bury_them_deep_lv0" in inv.hand

    def test_not_triggered_without_card_in_hand(self, game):
        inv = _setup(game)
        inv.hand.remove("bury_them_deep_lv0")
        game.damage_engine.deal_damage_to_enemy(
            "e1", 2, investigator_id="test_investigator",
        )
        assert game.state.scenario.victory_display == []
