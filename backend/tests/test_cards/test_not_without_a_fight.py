"""Tests for "Not without a fight!" (Level 0)."""

import pytest
from backend.cards.survivor.not_without_a_fight_lv0 import NotWithoutAFight
from backend.models.enums import ChaosTokenType, PlayerClass, Skill
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_enemy_data, make_investigator_data, make_location_data,
    make_skill_data,
)
from backend.engine.game import Game


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)
    inv_data = make_investigator_data(combat=2)
    g.register_card_data(inv_data)
    loc = make_location_data()
    g.register_card_data(loc)
    g.register_card_data(make_skill_data(
        id="not_without_a_fight_lv0", card_class=PlayerClass.SURVIVOR,
        skill_icons={"willpower": 1, "combat": 1, "agility": 1},
    ))
    g.register_card_data(make_enemy_data())
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)
    g.card_registry.register_class(NotWithoutAFight)
    return g


def _engage(game, count):
    inv = game.state.get_investigator("inv1")
    for i in range(count):
        iid = f"enemy_{i}"
        game.state.cards_in_play[iid] = CardInstance(
            instance_id=iid, card_id="test_enemy",
            owner_id="scenario", controller_id="scenario",
        )
        inv.threat_area.append(iid)


def _run(game, token=ChaosTokenType.ZERO):
    inv = game.state.get_investigator("inv1")
    inv.hand = ["not_without_a_fight_lv0"]
    game.chaos_bag.tokens = [token]
    return game.skill_test_engine.run_test(
        "inv1", Skill.COMBAT, 4, committed_card_ids=["not_without_a_fight_lv0"])


class TestNotWithoutAFight:
    def test_card_registered(self, game):
        assert "not_without_a_fight_lv0" in game.card_registry.registered_cards

    def test_plus_icons_per_engaged_enemy(self, game):
        """与2个敌人交战：印刷1战斗图标 + 每敌人+1 → 2+1+2=5 对 4 成功。"""
        _engage(game, 2)
        result = _run(game)
        assert result.success is True  # 2基础 +1印刷 +2交战 +0标记 = 5 >= 4
        assert result.committed_icons == 3  # 1印刷 + 2交战敌人

    def test_no_engaged_enemy_only_printed_icons(self, game):
        """无交战敌人：仅印刷图标生效（2+1=3 < 4 失败）。"""
        result = _run(game)
        assert result.success is False
        assert result.committed_icons == 1

    def test_single_engaged_enemy(self, game):
        """与1个敌人交战：2+1+1=4 对 4 成功。"""
        _engage(game, 1)
        result = _run(game)
        assert result.success is True
