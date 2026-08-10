"""Tests for Ever Vigilant (Level 1). (03023)

每次1张，打出你手牌中最多3张支援卡，每张资源费用减少1点。
"""

import pytest
from backend.cards.guardian.ever_vigilant_lv1 import EverVigilant
from backend.engine.game import Game
from backend.models.enums import Action, PlayerClass, SlotType
from backend.tests.conftest import (
    make_asset_data, make_event_data, make_investigator_data,
    make_location_data,
)


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)

    inv_data = make_investigator_data()
    g.register_card_data(inv_data)
    g.register_card_data(make_location_data())
    g.register_card_data(make_event_data(
        id="ever_vigilant_lv1", name="Ever Vigilant", cost=0,
    ))
    g.register_card_data(make_asset_data(
        id="machete_lv0", name="Machete", cost=3,
        card_class=PlayerClass.GUARDIAN, slots=[SlotType.HAND],
    ))
    g.register_card_data(make_asset_data(
        id="guard_dog_lv0", name="Guard Dog", cost=2,
        card_class=PlayerClass.GUARDIAN, slots=[SlotType.ALLY],
        health=3, sanity=1,
    ))
    g.register_card_data(make_asset_data(
        id="physical_training_lv0", name="Physical Training", cost=1,
        card_class=PlayerClass.GUARDIAN,
    ))
    g.register_card_data(make_asset_data(
        id="beat_cop_lv0", name="Beat Cop", cost=4,
        card_class=PlayerClass.GUARDIAN,
        health=2, sanity=2,
    ))

    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", g.state.get_card_data("test_location"), clues=2)
    g.card_registry.register_class(EverVigilant)

    inv = g.state.get_investigator("inv1")
    inv.hand.extend([
        "ever_vigilant_lv1", "machete_lv0", "guard_dog_lv0",
        "physical_training_lv0", "beat_cop_lv0",
    ])
    inv.resources = 4
    inv.actions_remaining = 3
    return g


class TestEverVigilant:
    def test_plays_up_to_3_assets_at_minus_1_cost(self, game):
        """自动按费用从高到低打出3张支援，各减1费：4+2+1 → 付3+1+0。"""
        inv = game.state.get_investigator("inv1")
        ok = game.action_resolver.perform_action(
            "inv1", Action.PLAY, card_id="ever_vigilant_lv1",
        )
        assert ok is True
        assert inv.resources == 4 - (3 + 1 + 0)

        played_ids = {
            game.state.get_card_instance(iid).card_id for iid in inv.play_area
        }
        assert played_ids == {"beat_cop_lv0", "guard_dog_lv0", "physical_training_lv0"}
        # 第4张（弯刀费用3→减后2，此时资源不足）留在手牌
        assert "machete_lv0" in inv.hand
        assert "ever_vigilant_lv1" in inv.discard

    def test_respects_resource_limit(self, game):
        """资源不足时跳过付不起的，继续打出付得起的（减费后）。"""
        inv = game.state.get_investigator("inv1")
        inv.resources = 1

        game.action_resolver.perform_action(
            "inv1", Action.PLAY, card_id="ever_vigilant_lv1",
        )
        # 减费后：巡警3（付不起）、弯刀2（付不起）、警犬1（打出）、训练0（打出）
        played_ids = {
            game.state.get_card_instance(iid).card_id for iid in inv.play_area
        }
        assert played_ids == {"guard_dog_lv0", "physical_training_lv0"}
        assert inv.resources == 0
        assert "machete_lv0" in inv.hand and "beat_cop_lv0" in inv.hand

    def test_no_assets_in_hand_is_noop(self, game):
        """手牌没有支援卡时不产生效果。"""
        inv = game.state.get_investigator("inv1")
        inv.hand = ["ever_vigilant_lv1"]

        ok = game.action_resolver.perform_action(
            "inv1", Action.PLAY, card_id="ever_vigilant_lv1",
        )
        assert ok is True
        assert inv.play_area == []
        assert inv.resources == 4
