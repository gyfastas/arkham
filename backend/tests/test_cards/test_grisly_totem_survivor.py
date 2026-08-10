"""Tests for Grisly Totem (Survivor Level 0 and Level 3, arkhamdb 05195).

注意：grisly_totem_lv3 存在同 id 的 Seeker 版本（05194，成功抽牌），
其实现与测试在 seeker 批次（test_grisly_totem.py）；本文件只测 Survivor
版本（05195，失败返回手牌）。
"""

import pytest
from backend.cards.survivor.grisly_totem_lv0 import GrislyTotem
from backend.cards.survivor.grisly_totem_lv3 import GrislyTotemLv3
from backend.models.enums import ChaosTokenType, PlayerClass, Skill, SlotType
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_asset_data, make_investigator_data, make_location_data,
    make_skill_data,
)
from backend.engine.game import Game


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)
    inv_data = make_investigator_data(willpower=3)
    g.register_card_data(inv_data)
    loc = make_location_data()
    g.register_card_data(loc)

    for cid in ("grisly_totem_lv0", "grisly_totem_lv3"):
        g.register_card_data(make_asset_data(
            id=cid, name=cid, cost=3, card_class=PlayerClass.SURVIVOR,
            slots=[SlotType.ACCESSORY], traits=["item", "charm"],
        ))
    g.register_card_data(make_skill_data(
        id="test_skill", skill_icons={"willpower": 1}))

    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)
    g.card_registry.register_class(GrislyTotem)
    g.card_registry.register_class(GrislyTotemLv3)
    return g


def _equip_totem(game, card_id="grisly_totem_lv0"):
    inv = game.state.get_investigator("inv1")
    iid = game.state.next_instance_id()
    game.state.cards_in_play[iid] = CardInstance(
        instance_id=iid, card_id=card_id,
        owner_id="inv1", controller_id="inv1",
        slot_used=[SlotType.ACCESSORY],
    )
    inv.play_area.append(iid)
    game.card_registry.activate_card(card_id, iid, game.event_bus)
    return iid


def _run_test(game, committed, token=ChaosTokenType.ZERO, difficulty=3):
    game.chaos_bag.tokens = [token]
    return game.skill_test_engine.run_test(
        "inv1", Skill.WILLPOWER, difficulty,
        committed_card_ids=committed,
    )


class TestGrislyTotemLv0:
    def test_card_registered(self, game):
        assert "grisly_totem_lv0" in game.card_registry.registered_cards
        assert "grisly_totem_lv3" in game.card_registry.registered_cards

    def test_commit_exhausts_and_adds_icon(self, game):
        """投入卡后：横置图腾，该卡再获得一个图标（+1）。"""
        totem_id = _equip_totem(game)
        inv = game.state.get_investigator("inv1")
        inv.hand = ["test_skill"]

        result = _run_test(game, ["test_skill"])

        # 意志3 + 图标1 + 图腾1 + 标记0 = 5
        assert result.committed_icons == 2
        assert result.modified_skill == 5
        inst = game.state.get_card_instance(totem_id)
        assert inst.exhausted is True

    def test_no_trigger_without_commit(self, game):
        totem_id = _equip_totem(game)
        result = _run_test(game, [])
        assert result.committed_icons == 0
        assert game.state.get_card_instance(totem_id).exhausted is False

    def test_no_trigger_when_exhausted(self, game):
        totem_id = _equip_totem(game)
        game.state.get_card_instance(totem_id).exhausted = True
        inv = game.state.get_investigator("inv1")
        inv.hand = ["test_skill"]

        result = _run_test(game, ["test_skill"])
        assert result.committed_icons == 1  # 仅卡牌自身图标


class TestGrislyTotemLv3:
    def test_failed_test_returns_card_to_hand(self, game):
        """检定失败：被加成的投入卡返回手牌而非弃置。"""
        _equip_totem(game, "grisly_totem_lv3")
        inv = game.state.get_investigator("inv1")
        inv.hand = ["test_skill"]

        # 难度6：意志3+图标1+图腾1+标记0=5 < 6，失败
        result = _run_test(game, ["test_skill"], difficulty=6)

        assert result.success is False
        assert "test_skill" in inv.hand
        assert "test_skill" not in inv.discard

    def test_successful_test_discards_committed_card(self, game):
        """检定成功：投入卡照常弃置。"""
        _equip_totem(game, "grisly_totem_lv3")
        inv = game.state.get_investigator("inv1")
        inv.hand = ["test_skill"]

        result = _run_test(game, ["test_skill"], difficulty=3)

        assert result.success is True
        assert "test_skill" in inv.discard
