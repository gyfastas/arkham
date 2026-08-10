"""Tests for Nephthys (Level 4). (07262)

+1意志；检定中将被移除的祝福改为封印在她上；
[快速]横置：释放3封印祝福，或返还3封印祝福对同地点敌人造成2伤害。
"""

import pytest
from backend.cards.guardian.nephthys_lv4 import Nephthys
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import (
    ChaosTokenType, GameEvent, PlayerClass, Skill, SlotType,
)
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_asset_data, make_enemy_data, make_investigator_data,
    make_location_data,
)


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)
    inv_data = make_investigator_data(willpower=3)
    g.register_card_data(inv_data)
    g.register_card_data(make_location_data())
    g.register_card_data(make_asset_data(
        id="nephthys_lv4", name="Nephthys", cost=3,
        card_class=PlayerClass.GUARDIAN, slots=[SlotType.ALLY],
        traits=["ally", "blessed"], health=2, sanity=2,
    ))
    g.register_card_data(make_enemy_data(fight=3, health=10))

    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", g.state.get_card_data("test_location"), clues=0)
    g.card_registry.register_class(Nephthys)

    inv = g.state.get_investigator("inv1")
    inst = CardInstance(
        instance_id="neph_1", card_id="nephthys_lv4",
        owner_id="inv1", controller_id="inv1", slot_used=[SlotType.ALLY],
    )
    g.state.cards_in_play["neph_1"] = inst
    inv.play_area.append("neph_1")
    impl = g.card_registry.activate_card(
        "nephthys_lv4", "neph_1", g.event_bus, chaos_bag=g.chaos_bag)
    return g, impl


class TestNephthys:
    def test_willpower_bonus(self, game):
        g, _ = game
        assert g.preview_skill_bonuses("inv1").get("willpower") == 1

    def test_seals_bless_revealed_in_test(self, game):
        """检定中结算到祝福：改为封印在纳芙蒂斯上。"""
        g, _ = game
        g.chaos_bag.add_token(ChaosTokenType.BLESS)
        ctx = EventContext(
            game_state=g.state, event=GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="inv1", skill_type=Skill.WILLPOWER,
            chaos_token=ChaosTokenType.BLESS, amount=2,
        )
        g.event_bus.emit(ctx)
        inst = g.state.get_card_instance("neph_1")
        assert inst.uses["sealed"] == 1
        assert g.chaos_bag.sealed.count(ChaosTokenType.BLESS) == 1
        assert g.chaos_bag.tokens.count(ChaosTokenType.BLESS) == 0

    def test_release_3_sealed(self, game):
        """[快速]释放：3个封印祝福回到袋中。"""
        g, impl = game
        inst = g.state.get_card_instance("neph_1")
        for _ in range(3):
            g.chaos_bag.add_token(ChaosTokenType.BLESS)
            g.chaos_bag.seal_token(ChaosTokenType.BLESS)
        inst.uses["sealed"] = 3

        assert impl.activate(g.state, "inv1", mode="release") is True
        assert inst.uses["sealed"] == 0
        assert inst.exhausted is True
        assert g.chaos_bag.tokens.count(ChaosTokenType.BLESS) == 3
        assert g.chaos_bag.sealed.count(ChaosTokenType.BLESS) == 0

    def test_return_3_sealed_to_deal_damage(self, game):
        """[快速]返还供应堆：对同地点敌人造成2伤害，标记离开游戏。"""
        g, impl = game
        inst = g.state.get_card_instance("neph_1")
        for _ in range(3):
            g.chaos_bag.add_token(ChaosTokenType.BLESS)
            g.chaos_bag.seal_token(ChaosTokenType.BLESS)
        inst.uses["sealed"] = 3
        g.state.cards_in_play["enemy_1"] = CardInstance(
            instance_id="enemy_1", card_id="test_enemy",
            owner_id="scenario", controller_id="scenario",
        )
        g.state.get_investigator("inv1").threat_area.append("enemy_1")

        assert impl.activate(g.state, "inv1", mode="damage") is True
        assert g.state.get_card_instance("enemy_1").damage == 2
        assert inst.uses["sealed"] == 0
        # 返回供应堆：既不在袋中也不在封印列表
        assert g.chaos_bag.tokens.count(ChaosTokenType.BLESS) == 0
        assert g.chaos_bag.sealed.count(ChaosTokenType.BLESS) == 0

    def test_requires_3_sealed(self, game):
        """封印不足3个：不可用。"""
        g, impl = game
        g.state.get_card_instance("neph_1").uses["sealed"] = 2
        assert impl.activate(g.state, "inv1", mode="release") is False
