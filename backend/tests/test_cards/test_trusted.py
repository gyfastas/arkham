"""Tests for Trusted (Level 0). (04019)

快速事件：叠加到你控制的一张盟友支援；被叠加的支援生命+1、神智+1。
"""

import pytest
from backend.cards.guardian.trusted_lv0 import Trusted
from backend.engine.game import Game
from backend.models.enums import Action, PlayerClass, SlotType
from backend.models.state import CardInstance
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
    g.register_card_data(make_asset_data(
        id="beat_cop_lv0", name="Beat Cop", cost=4,
        card_class=PlayerClass.GUARDIAN,
        slots=[SlotType.ALLY], health=2, sanity=1,
        traits=["ally", "police"],
    ))
    g.register_card_data(make_asset_data(
        id="flashlight_lv0", name="Flashlight", cost=2,
        slots=[SlotType.HAND], traits=["item", "tool"],
    ))
    g.register_card_data(make_event_data(
        id="trusted_lv0", name="Trusted", cost=1,
        card_class=PlayerClass.GUARDIAN, fast=True,
    ))

    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", g.state.get_card_data("test_location"))
    g.card_registry.register_class(Trusted)

    inv = g.state.get_investigator("inv1")
    inv.hand.append("trusted_lv0")
    inv.actions_remaining = 3
    return g


def _deploy(game, card_id, instance_id):
    game.state.cards_in_play[instance_id] = CardInstance(
        instance_id=instance_id, card_id=card_id,
        owner_id="inv1", controller_id="inv1",
    )
    game.state.get_investigator("inv1").play_area.append(instance_id)
    return game.state.cards_in_play[instance_id]


def _attachments_on(game, target_iid):
    return [ci for ci in game.state.cards_in_play.values()
            if ci.attached_to == target_iid]


class TestTrusted:
    def test_attach_gives_plus1_health_sanity(self, game):
        """打出后叠加到盟友：盟友 CardData 生命/神智 +1。"""
        _deploy(game, "beat_cop_lv0", "cop_1")
        cd = game.state.get_card_data("beat_cop_lv0")

        ok = game.action_resolver.perform_action(
            "inv1", Action.PLAY, card_id="trusted_lv0",
        )
        assert ok is True
        assert (cd.health, cd.sanity) == (3, 2)
        attachments = _attachments_on(game, "cop_1")
        assert len(attachments) == 1
        assert attachments[0].card_id == "trusted_lv0"

    def test_bonus_lets_ally_survive(self, game):
        """+1生命使盟友能承受原本致死的2点伤害。"""
        _deploy(game, "beat_cop_lv0", "cop_1")
        game.action_resolver.perform_action(
            "inv1", Action.PLAY, card_id="trusted_lv0",
        )

        game.damage_engine.deal_damage(
            "inv1", damage=2, damage_assignment={"cop_1": 2},
        )
        cop = game.state.get_card_instance("cop_1")
        assert cop is not None  # 2伤害 < 3生命，存活
        assert cop.damage == 2

    def test_ally_leaves_reverts_bonus(self, game):
        """盟友被击败离场：+1/+1 移除，叠加实例清理。"""
        _deploy(game, "beat_cop_lv0", "cop_1")
        game.action_resolver.perform_action(
            "inv1", Action.PLAY, card_id="trusted_lv0",
        )
        cd = game.state.get_card_data("beat_cop_lv0")
        assert (cd.health, cd.sanity) == (3, 2)

        # 3点伤害击败（3 >= 3）
        game.damage_engine.deal_damage(
            "inv1", damage=3, damage_assignment={"cop_1": 3},
        )
        assert game.state.get_card_instance("cop_1") is None
        assert (cd.health, cd.sanity) == (2, 1)  # 加值恢复
        assert _attachments_on(game, "cop_1") == []

    def test_no_ally_fizzles(self, game):
        """场上没有盟友：不结算叠加（只有道具时不选）。"""
        _deploy(game, "flashlight_lv0", "light_1")
        cd = game.state.get_card_data("flashlight_lv0")

        game.action_resolver.perform_action(
            "inv1", Action.PLAY, card_id="trusted_lv0",
        )
        assert _attachments_on(game, "light_1") == []
        assert cd.health is None  # 未被修改
