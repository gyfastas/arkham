"""Tests for True Grit (Level 0). (03021)

你所在地点的其他调查员受到的伤害可以分配给勇气过人（生命3）。
"""

import pytest
from backend.cards.guardian.true_grit_lv0 import TrueGrit
from backend.engine.game import Game
from backend.models.enums import CardType, PlayerClass
from backend.models.state import CardData, CardInstance
from backend.tests.conftest import (
    make_investigator_data, make_location_data,
)


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)

    inv_data = make_investigator_data()
    g.register_card_data(inv_data)
    inv_data2 = make_investigator_data(id="inv2_card", name="Second")
    g.register_card_data(inv_data2)
    g.register_card_data(make_location_data())
    g.register_card_data(make_location_data(id="far_location", name="Far"))
    g.register_card_data(CardData(
        id="true_grit_lv0", name="True Grit", name_cn="勇气过人",
        type=CardType.ASSET, card_class=PlayerClass.GUARDIAN, cost=3,
        traits=["talent"], health=3, skill_icons={"willpower": 1},
    ))

    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_investigator("inv2", inv_data2, starting_location="test_location")
    g.add_location("test_location", g.state.get_card_data("test_location"), clues=2)
    g.add_location("far_location", g.state.get_card_data("far_location"), clues=0)
    g.card_registry.register_class(TrueGrit)

    inv1 = g.state.get_investigator("inv1")
    inst = CardInstance(
        instance_id="grit_1", card_id="true_grit_lv0",
        owner_id="inv1", controller_id="inv1",
    )
    g.state.cards_in_play["grit_1"] = inst
    inv1.play_area.append("grit_1")
    g.card_registry.activate_card("true_grit_lv0", "grit_1", g.event_bus)
    return g


class TestTrueGrit:
    def test_soaks_damage_for_other_investigator(self, game):
        """同地点另一位调查员受2点伤害：全部由勇气过人承担。"""
        inst = game.state.get_card_instance("grit_1")
        inv2 = game.state.get_investigator("inv2")

        game.damage_engine.deal_damage("inv2", damage=2)
        assert inst.damage == 2
        assert inv2.damage == 0

    def test_overflow_hits_investigator_and_defeats_grit(self, game):
        """超出剩余生命的部分由对方承担；承伤达到上限被击败。"""
        inst = game.state.get_card_instance("grit_1")
        inst.damage = 2  # 剩余生命1
        inv2 = game.state.get_investigator("inv2")
        inv1 = game.state.get_investigator("inv1")

        game.damage_engine.deal_damage("inv2", damage=2)
        # 1点由勇气过人承担（共3点，被击败），另1点由 inv2 承担
        assert "grit_1" not in inv1.play_area
        assert "true_grit_lv0" in inv1.discard
        assert inv2.damage == 1

    def test_no_soak_at_different_location(self, game):
        """不同地点的调查员受伤不分担。"""
        inst = game.state.get_card_instance("grit_1")
        inv2 = game.state.get_investigator("inv2")
        inv2.location_id = "far_location"

        game.damage_engine.deal_damage("inv2", damage=2)
        assert inst.damage == 0
        assert inv2.damage == 2

    def test_no_soak_for_own_damage(self, game):
        """持有者自己的伤害不触发（走正常分配通道）。"""
        inst = game.state.get_card_instance("grit_1")
        inv1 = game.state.get_investigator("inv1")

        game.damage_engine.deal_damage("inv1", damage=2)
        assert inst.damage == 0
        assert inv1.damage == 2
