"""Tests for Tetsuo Mori (Level 0). (06155)

伤害/恐惧可分配给森哲夫（引擎 damage_assignment 通道）；被击败时：
所选调查员在弃牌堆或牌堆顶9张中查找一张道具支援卡加入手牌。
"""

import pytest
from backend.cards.guardian.tetsuo_mori_lv0 import TetsuoMori
from backend.engine.game import Game
from backend.models.enums import PlayerClass, SlotType
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_asset_data, make_investigator_data, make_location_data,
)


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)

    inv_data = make_investigator_data()
    g.register_card_data(inv_data)
    g.register_card_data(make_location_data())
    g.register_card_data(make_asset_data(
        id="tetsuo_mori_lv0", name="Tetsuo Mori", cost=3,
        card_class=PlayerClass.GUARDIAN,
        slots=[SlotType.ALLY], health=2, sanity=2,
        traits=["ally", "police"], skill_icons={"intellect": 1},
    ))
    g.register_card_data(make_asset_data(
        id="flashlight_lv0", name="Flashlight", cost=2,
        slots=[SlotType.HAND], traits=["item", "tool"], uses={"supplies": 3},
    ))
    g.register_card_data(make_asset_data(
        id="beat_cop_lv0", name="Beat Cop", cost=4,
        slots=[SlotType.ALLY], health=3, sanity=2, traits=["ally", "police"],
    ))

    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_investigator("inv2", make_investigator_data(),
                       starting_location="test_location")
    g.add_location("test_location", g.state.get_card_data("test_location"))
    g.card_registry.register_class(TetsuoMori)
    return g


def _deploy_tetsuo(game, owner="inv1"):
    inst_id = game.state.next_instance_id()
    game.state.cards_in_play[inst_id] = CardInstance(
        instance_id=inst_id, card_id="tetsuo_mori_lv0",
        owner_id=owner, controller_id=owner,
        slot_used=[SlotType.ALLY],
    )
    game.state.get_investigator(owner).play_area.append(inst_id)
    game.card_registry.activate_card("tetsuo_mori_lv0", inst_id, game.event_bus)
    return inst_id


class TestTetsuoMori:
    def test_soak_damage_for_other_investigator(self, game):
        """同地点其他调查员受到的伤害可分配给森哲夫。"""
        tetsuo_id = _deploy_tetsuo(game)
        game.damage_engine.deal_damage(
            "inv2", damage=2, damage_assignment={tetsuo_id: 1},
        )
        tetsuo = game.state.get_card_instance(tetsuo_id)
        inv2 = game.state.get_investigator("inv2")
        assert tetsuo.damage == 1
        assert inv2.damage == 1  # 2 - 1 分配给森哲夫

    def test_defeat_searches_discard_for_item(self, game):
        """被击败时：默认拥有者从弃牌堆找到道具支援加入手牌。"""
        tetsuo_id = _deploy_tetsuo(game)
        inv1 = game.state.get_investigator("inv1")
        inv1.discard.extend(["beat_cop_lv0", "flashlight_lv0"])

        # 2点伤害分配给森哲夫 → 击败
        game.damage_engine.deal_damage(
            "inv2", damage=2, damage_assignment={tetsuo_id: 2},
        )

        assert game.state.get_card_instance(tetsuo_id) is None  # 已离场
        assert "flashlight_lv0" in inv1.hand  # 道具入手
        assert "flashlight_lv0" not in inv1.discard
        assert "beat_cop_lv0" in inv1.discard  # 非道具不动

    def test_defeat_searches_top9_of_deck(self, game):
        """弃牌堆无道具时：查牌堆顶9张并混洗（抽到即入手的唯一道具在第5张）。"""
        tetsuo_id = _deploy_tetsuo(game)
        inv1 = game.state.get_investigator("inv1")
        inv1.deck = ["beat_cop_lv0"] * 4 + ["flashlight_lv0"] + [
            "beat_cop_lv0"] * 10
        deck_before = len(inv1.deck)

        game.damage_engine.deal_damage(
            "inv2", damage=2, damage_assignment={tetsuo_id: 2},
        )

        assert "flashlight_lv0" in inv1.hand
        assert len(inv1.deck) == deck_before - 1  # 找到并移除后混洗

    def test_no_item_noop(self, game):
        """弃牌堆与牌堆顶9张都没有道具：仅离场，无查找效果。"""
        tetsuo_id = _deploy_tetsuo(game)
        inv1 = game.state.get_investigator("inv1")
        inv1.deck = ["beat_cop_lv0"] * 12

        game.damage_engine.deal_damage(
            "inv2", damage=2, damage_assignment={tetsuo_id: 2},
        )
        assert game.state.get_card_instance(tetsuo_id) is None
        assert inv1.hand == []
