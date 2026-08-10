"""Tests for A Chance Encounter (Level 2)."""

import pytest
from backend.cards.survivor.a_chance_encounter_lv2 import AChanceEncounter
from backend.models.enums import Action, PlayerClass, SlotType
from backend.tests.conftest import (
    make_asset_data, make_event_data, make_investigator_data,
    make_location_data,
)
from backend.engine.game import Game


@pytest.fixture
def game():
    g = Game("test")
    inv_data = make_investigator_data()
    g.register_card_data(inv_data)
    loc = make_location_data()
    g.register_card_data(loc)
    # 数据沿用实际 JSON 的可变费用编码：cost=-2 表示 X
    g.register_card_data(make_event_data(
        id="a_chance_encounter_lv2", name="A Chance Encounter", cost=-2,
        card_class=PlayerClass.SURVIVOR,
    ))
    g.register_card_data(make_asset_data(
        id="ally_cheap", name="Cheap Ally", cost=2,
        slots=[SlotType.ALLY], traits=["ally"], health=2, sanity=2,
    ))
    g.register_card_data(make_asset_data(
        id="ally_costly", name="Costly Ally", cost=4,
        slots=[SlotType.ALLY], traits=["ally"], health=2, sanity=2,
    ))
    g.register_card_data(make_asset_data(
        id="not_ally", name="Flashlight", cost=2, traits=["item"],
    ))
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)
    g.card_registry.register_class(AChanceEncounter)
    return g


def _play(game):
    inv = game.state.get_investigator("inv1")
    inv.actions_remaining = 3
    return game.action_resolver.perform_action(
        "inv1", Action.PLAY, card_id="a_chance_encounter_lv2")


class TestAChanceEncounter:
    def test_card_registered(self, game):
        assert "a_chance_encounter_lv2" in game.card_registry.registered_cards

    def test_puts_highest_affordable_ally_into_play(self, game):
        """净支出 X=盟友打印费用，盟友从你的弃牌堆入场。"""
        inv = game.state.get_investigator("inv1")
        inv.hand = ["a_chance_encounter_lv2"]
        inv.resources = 5
        inv.discard = ["ally_cheap", "ally_costly", "not_ally"]

        assert _play(game) is True
        # 付得起的最高费用盟友（4费）入场；净支出 5-4=1
        assert inv.resources == 1
        assert "ally_costly" not in inv.discard
        assert "ally_cheap" in inv.discard
        assert "not_ally" in inv.discard
        inst = next(
            ci for ci in game.state.cards_in_play.values()
            if ci.card_id == "ally_costly")
        assert inst.controller_id == "inv1"
        assert inst.instance_id in inv.play_area
        # 占用盟友槽
        mgr = game.state.slot_managers["inv1"]
        assert mgr.available(SlotType.ALLY) == 0

    def test_respects_affordability(self, game):
        """资源只够2费盟友时选2费的。"""
        inv = game.state.get_investigator("inv1")
        inv.hand = ["a_chance_encounter_lv2"]
        inv.resources = 2
        inv.discard = ["ally_cheap", "ally_costly"]

        assert _play(game) is True
        assert inv.resources == 0  # 净支出2
        assert "ally_cheap" not in inv.discard
        assert "ally_costly" in inv.discard
        assert any(ci.card_id == "ally_cheap"
                   for ci in game.state.cards_in_play.values())

    def test_can_target_other_players_discard(self, game):
        """可选择任意玩家弃牌堆中的盟友。"""
        inv2_data = make_investigator_data(id="inv2", name="Second")
        game.register_card_data(inv2_data)
        game.add_investigator("inv2", inv2_data, starting_location="test_location")
        inv1 = game.state.get_investigator("inv1")
        inv2 = game.state.get_investigator("inv2")
        inv1.hand = ["a_chance_encounter_lv2"]
        inv1.resources = 3
        inv2.discard = ["ally_cheap"]

        assert _play(game) is True
        assert inv1.resources == 1  # 净支出2
        assert "ally_cheap" not in inv2.discard
        inst = next(
            ci for ci in game.state.cards_in_play.values()
            if ci.card_id == "ally_cheap")
        # 置于你的控制之下（所有者从简为打出者，见卡内注释）
        assert inst.controller_id == "inv1"
        assert inst.instance_id in inv1.play_area

    def test_fizzles_without_legal_target(self, game):
        """无合法目标：引擎误收的费用被退回，效果落空。"""
        inv = game.state.get_investigator("inv1")
        inv.hand = ["a_chance_encounter_lv2"]
        inv.resources = 5
        inv.discard = ["not_ally"]

        assert _play(game) is True
        assert inv.resources == 5  # 未支付任何 X
        assert "a_chance_encounter_lv2" in inv.discard  # 事件照常入弃牌堆
        assert not any(ci.card_id == "not_ally"
                       for ci in game.state.cards_in_play.values())
