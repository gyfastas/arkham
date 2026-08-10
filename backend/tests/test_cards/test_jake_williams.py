"""Tests for Jake Williams (Level 0)."""

import pytest
from backend.cards.neutral.jake_williams_lv0 import JakeWilliams
from backend.engine.game import Game
from backend.models.enums import Action
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_asset_data, make_enemy_data, make_investigator_data,
    make_location_data,
)


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)
    g.register_card_data(make_investigator_data())
    g.register_card_data(make_location_data(connections=["loc2"]))
    g.register_card_data(make_location_data(
        id="loc2", name="Loc2", connections=["test_location"],
    ))
    g.register_card_data(make_asset_data(
        id="jake_williams_lv0", name="Jake Williams", cost=3,
    ))
    g.register_card_data(make_enemy_data(
        id="ghoul", name="Ghoul", damage=2, horror=0,
    ))
    g.add_investigator("inv1", g.state.get_card_data("test_investigator"),
                       starting_location="test_location")
    g.add_location("test_location", g.state.get_card_data("test_location"))
    g.add_location("loc2", g.state.get_card_data("loc2"))
    g.card_registry.register_class(JakeWilliams)
    inv = g.state.get_investigator("inv1")
    inv.hand.append("jake_williams_lv0")
    inv.resources = 5
    inv.deck = ["guts_lv0"]

    # 敌人初始在地点上未交战（避免打出杰克时的借机攻击干扰断言）
    enemy = CardInstance(
        instance_id="enemy_1", card_id="ghoul",
        owner_id="scenario", controller_id="scenario",
    )
    g.state.cards_in_play["enemy_1"] = enemy
    g.state.get_location("test_location").enemies.append("enemy_1")
    return g


def _play(game):
    game.action_resolver.perform_action(
        "inv1", Action.PLAY, card_id="jake_williams_lv0",
    )
    return next(
        i for i in game.card_registry.active_instances.values()
        if isinstance(i, JakeWilliams)
    )


class TestJakeWilliams:
    def test_first_move_no_aoo_second_move_provokes(self, game):
        """每回合首个移动不引发借机攻击；第二个移动正常引发。"""
        _play(game)
        inv = game.state.get_investigator("inv1")
        # 打出后敌人才交战
        game.state.get_location("test_location").enemies.remove("enemy_1")
        inv.threat_area.append("enemy_1")
        game.action_resolver.perform_action(
            "inv1", Action.MOVE, destination="loc2",
        )
        assert inv.damage == 0  # 首个移动：借机攻击被取消
        # 敌人跟随交战（仍在威胁区），第二个移动引发借机攻击
        game.action_resolver.perform_action(
            "inv1", Action.MOVE, destination="test_location",
        )
        assert inv.damage == 2

    def test_draw_on_location_revealed(self, game):
        """[reaction] 地点揭示后：横置抽1张牌。"""
        impl = _play(game)
        inv = game.state.get_investigator("inv1")
        assert impl.on_location_revealed(game.state, "inv1") is True
        assert "guts_lv0" in inv.hand
        inst = game.state.get_card_instance(impl.instance_id)
        assert inst.exhausted is True
