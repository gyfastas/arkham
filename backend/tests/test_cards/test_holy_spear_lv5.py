"""Tests for Holy Spear (Level 5). (07302)

[行动]攻击+2战斗/+1伤害（可释放1封印祝福）；
[行动]封印2祝福后攻击+4战斗/+2伤害。
"""

import pytest
from backend.cards.guardian.holy_spear_lv5 import HolySpear
from backend.engine.game import Game
from backend.models.enums import (
    Action, CardType, ChaosTokenType, PlayerClass, SlotType,
)
from backend.models.state import CardData, CardInstance
from backend.tests.conftest import (
    make_enemy_data, make_investigator_data, make_location_data,
)


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)

    inv_data = make_investigator_data(combat=3)
    g.register_card_data(inv_data)
    g.register_card_data(make_location_data())
    g.register_card_data(CardData(
        id="holy_spear_lv5", name="Holy Spear", name_cn="圣枪",
        type=CardType.ASSET, card_class=PlayerClass.GUARDIAN, cost=4,
        slots=[SlotType.HAND, SlotType.HAND],
        traits=["item", "weapon", "melee", "blessed"],
    ))
    g.register_card_data(make_enemy_data(fight=3, health=10))

    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", g.state.get_card_data("test_location"), clues=0)
    g.card_registry.register_class(HolySpear)
    return g


def _setup(game):
    inv = game.state.get_investigator("inv1")
    weapon = game.state.next_instance_id()
    game.state.cards_in_play[weapon] = CardInstance(
        instance_id=weapon, card_id="holy_spear_lv5",
        owner_id="inv1", controller_id="inv1",
        slot_used=[SlotType.HAND, SlotType.HAND],
    )
    inv.play_area.append(weapon)
    impl = game.card_registry.activate_card(
        "holy_spear_lv5", weapon, game.event_bus, chaos_bag=game.chaos_bag)
    game.state.cards_in_play["enemy_1"] = CardInstance(
        instance_id="enemy_1", card_id="test_enemy",
        owner_id="scenario", controller_id="scenario",
    )
    inv.threat_area.append("enemy_1")
    inv.actions_remaining = 3
    return weapon, impl


class TestHolySpear:
    def test_basic_fight_bonus(self, game):
        """普通攻击：+2战斗/+1伤害（徒手基础1+1=2）。"""
        weapon, impl = _setup(game)
        assert impl.activate_fight(game.state, "inv1") is True
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]
        # 战斗 3+2=5 vs 3 → 成功，伤害 1+1=2
        game.action_resolver.perform_action(
            "inv1", Action.FIGHT,
            enemy_instance_id="enemy_1", weapon_instance_id=weapon,
        )
        assert game.state.get_card_instance("enemy_1").damage == 2

    def test_seal_fight_bonus(self, game):
        """封印攻击：袋中封印2祝福，+4战斗/+2伤害。"""
        weapon, impl = _setup(game)
        game.chaos_bag.add_token(ChaosTokenType.BLESS)
        game.chaos_bag.add_token(ChaosTokenType.BLESS)
        assert impl.activate_seal_fight(game.state, "inv1") is True
        inst = game.state.get_card_instance(weapon)
        assert inst.uses["sealed"] == 2
        assert game.chaos_bag.tokens.count(ChaosTokenType.BLESS) == 0
        assert game.chaos_bag.sealed.count(ChaosTokenType.BLESS) == 2

        game.chaos_bag.tokens = [ChaosTokenType.ZERO]
        # 战斗 3+4=7 vs 3 → 成功，伤害 1+2=3
        game.action_resolver.perform_action(
            "inv1", Action.FIGHT,
            enemy_instance_id="enemy_1", weapon_instance_id=weapon,
        )
        assert game.state.get_card_instance("enemy_1").damage == 3

    def test_seal_fight_requires_two_bless(self, game):
        """袋中不足2个祝福：封印攻击不可用。"""
        weapon, impl = _setup(game)
        game.chaos_bag.add_token(ChaosTokenType.BLESS)
        assert impl.activate_seal_fight(game.state, "inv1") is False
        assert game.state.get_card_instance(weapon).uses.get("sealed", 0) == 0

    def test_release_sealed_on_fight(self, game):
        """普通攻击时释放1个封印祝福回袋。"""
        weapon, impl = _setup(game)
        inst = game.state.get_card_instance(weapon)
        game.chaos_bag.add_token(ChaosTokenType.BLESS)
        game.chaos_bag.seal_token(ChaosTokenType.BLESS)
        inst.uses["sealed"] = 1

        assert impl.activate_fight(game.state, "inv1", release=True) is True
        assert inst.uses["sealed"] == 0
        assert game.chaos_bag.tokens.count(ChaosTokenType.BLESS) == 1
        assert game.chaos_bag.sealed.count(ChaosTokenType.BLESS) == 0
