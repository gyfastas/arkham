"""Tests for Resourceful (Level 0)."""

import pytest
from backend.cards.survivor.resourceful_lv0 import Resourceful
from backend.models.enums import ChaosTokenType, PlayerClass, Skill
from backend.tests.conftest import (
    make_event_data, make_investigator_data, make_location_data,
    make_skill_data,
)
from backend.engine.game import Game


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)
    inv_data = make_investigator_data(intellect=3)
    g.register_card_data(inv_data)
    loc = make_location_data()
    g.register_card_data(loc)
    g.register_card_data(make_skill_data(
        id="resourceful_lv0", card_class=PlayerClass.SURVIVOR,
        skill_icons={"intellect": 1, "combat": 1, "agility": 1},
    ))
    g.register_card_data(make_event_data(
        id="lucky_lv0", name="Lucky!", cost=1,
        card_class=PlayerClass.SURVIVOR,
    ))
    g.register_card_data(make_event_data(
        id="emergency_cache_lv0", name="Emergency Cache", cost=0,
        card_class=PlayerClass.NEUTRAL,
    ))
    g.register_card_data(make_skill_data(
        id="resourceful_lv0_copy", card_class=PlayerClass.SURVIVOR,
    ))
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)
    g.card_registry.register_class(Resourceful)
    return g


def _run_test(game, token, committed):
    game.chaos_bag.tokens = [token]
    return game.skill_test_engine.run_test(
        "inv1", Skill.INTELLECT, 2, committed_card_ids=committed)


class TestResourceful:
    def test_card_registered(self, game):
        assert "resourceful_lv0" in game.card_registry.registered_cards

    def test_recovers_survivor_card_on_success(self, game):
        """检定成功：回收弃牌堆中一张生存者卡（急中生智本身除外）。"""
        inv = game.state.get_investigator("inv1")
        inv.hand = ["resourceful_lv0"]
        inv.discard = ["lucky_lv0"]

        result = _run_test(game, ChaosTokenType.PLUS_1, ["resourceful_lv0"])
        assert result.success is True
        assert "lucky_lv0" in inv.hand
        assert "lucky_lv0" not in inv.discard
        # 急中生智按规则在结算后入弃牌堆
        assert "resourceful_lv0" in inv.discard

    def test_no_recovery_on_failure(self, game):
        inv = game.state.get_investigator("inv1")
        inv.hand = ["resourceful_lv0"]
        inv.discard = ["lucky_lv0"]

        result = _run_test(game, ChaosTokenType.AUTO_FAIL, ["resourceful_lv0"])
        assert result.success is False
        assert "lucky_lv0" in inv.discard
        assert "lucky_lv0" not in inv.hand

    def test_skips_neutral_and_resourceful_named_cards(self, game):
        """中立卡与同名卡不可回收。"""
        inv = game.state.get_investigator("inv1")
        inv.hand = ["resourceful_lv0"]
        inv.discard = ["emergency_cache_lv0"]

        # 弃牌堆里放另一张"Resourceful"（同名不可回收）：
        # 用同名数据卡覆盖 copy 的注册名
        game.state.card_database["resourceful_lv0_copy"].name = "Resourceful"
        inv.discard.append("resourceful_lv0_copy")

        result = _run_test(game, ChaosTokenType.PLUS_1, ["resourceful_lv0"])
        assert result.success is True
        assert "emergency_cache_lv0" in inv.discard
        assert "resourceful_lv0_copy" in inv.discard
        assert result.extra.get("resourceful_recovered") is None

    def test_no_recovery_when_not_committed(self, game):
        inv = game.state.get_investigator("inv1")
        inv.discard = ["lucky_lv0"]

        result = _run_test(game, ChaosTokenType.PLUS_1, [])
        assert result.success is True
        assert "lucky_lv0" in inv.discard
