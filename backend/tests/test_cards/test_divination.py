"""Tests for Divination (Level 1 & 4). (08101 / 08103)

[行动]调查：可用意志代替智力并+技能值；成功花1..N充能，每充能1条线索；
0点差值成功则弃手牌（lv1弃1/lv4弃2）。
"""

import pytest

from backend.cards.seeker.divination_lv1 import Divination
from backend.cards.seeker.divination_lv4 import DivinationLv4
from backend.engine.game import Game
from backend.models.enums import Action, ChaosTokenType
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_asset_data, make_investigator_data, make_location_data,
    make_skill_data,
)


@pytest.fixture(params=["divination_lv1", "divination_lv4"])
def game(request):
    card_id = request.param
    g = Game(f"test_{card_id}")
    g.chaos_bag.seed(42)
    inv_data = make_investigator_data(intellect=3, willpower=5)
    g.register_card_data(inv_data)
    loc_data = make_location_data(id="loc_a", shroud=2)
    g.register_card_data(loc_data)
    g.add_investigator("inv1", inv_data, starting_location="loc_a")
    g.add_location("loc_a", loc_data, clues=3)
    g.register_card_data(make_skill_data(id="filler", name="filler"))
    charges = 4 if card_id == "divination_lv1" else 6
    g.register_card_data(make_asset_data(
        id=card_id, traits=["spell", "augury"], uses={"chargess": charges}))
    inst = CardInstance(
        instance_id="inst_div", card_id=card_id,
        owner_id="inv1", controller_id="inv1",
    )
    inst.uses = {"chargess": charges}  # 数据双 s 键兼容
    g.state.cards_in_play["inst_div"] = inst
    g.state.get_investigator("inv1").play_area.append("inst_div")
    cls = Divination if card_id == "divination_lv1" else DivinationLv4
    impl = cls("inst_div")
    impl.register(g.event_bus, "inst_div")
    return g, inst, impl, card_id


class TestDivination:
    def test_willpower_substitute_and_charge_clues(self, game):
        """意志代替智力+加值；成功花满充能：每充能1条线索。"""
        g, inst, impl, card_id = game
        max_spend = 2 if card_id == "divination_lv1" else 3
        bonus = 1 if card_id == "divination_lv1" else 2
        g.chaos_bag.tokens = [ChaosTokenType.ZERO]
        inv = g.state.get_investigator("inv1")
        loc = g.state.locations["loc_a"]

        assert impl.activate(g.state, "inv1") is True
        assert g.action_resolver.perform_action("inv1", Action.INVESTIGATE)
        # 5意志代替3智力 +bonus vs 隐蔽2 → 成功
        # 花满充能：基础1 + (max_spend-1) 额外
        assert inv.clues == max_spend
        assert loc.clues == 3 - max_spend
        assert inst.uses["chargess"] == (4 if card_id == "divination_lv1"
                                         else 6) - max_spend

    def test_intellect_without_substitute(self, game):
        """选择不用意志：智力3+加值对隐蔽2仍成功，花1充能→1条线索。"""
        g, inst, impl, card_id = game
        g.chaos_bag.tokens = [ChaosTokenType.ZERO]
        inv = g.state.get_investigator("inv1")

        impl.activate(g.state, "inv1", use_willpower=False, charges=1)
        g.action_resolver.perform_action("inv1", Action.INVESTIGATE)
        assert inv.clues == 1

    def test_succeed_by_zero_discards(self, game):
        """0点差值成功：弃1张手牌（lv4弃2张）。"""
        g, inst, impl, card_id = game
        g.chaos_bag.tokens = [ChaosTokenType.ZERO]
        inv = g.state.get_investigator("inv1")
        bonus = 1 if card_id == "divination_lv1" else 2
        # 调整隐蔽使差值为0：智力3+bonus vs 隐蔽(3+bonus)
        g.state.locations["loc_a"].card_data.shroud = 3 + bonus
        discards = 1 if card_id == "divination_lv1" else 2
        inv.hand = ["filler"] * discards

        impl.activate(g.state, "inv1", use_willpower=False)
        g.action_resolver.perform_action("inv1", Action.INVESTIGATE)
        assert inv.hand == []
        assert inv.discard.count("filler") == discards
