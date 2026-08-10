"""Tests for Lantern (Level 0)."""

import pytest
from backend.cards.survivor.lantern_lv0 import Lantern
from backend.models.enums import Action, ChaosTokenType, PlayerClass, SlotType
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_asset_data, make_enemy_data, make_investigator_data, make_location_data,
)
from backend.engine.game import Game


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)
    inv_data = make_investigator_data(intellect=3)
    g.register_card_data(inv_data)
    loc = make_location_data(shroud=4, clue_value=3)
    g.register_card_data(loc)
    g.register_card_data(make_asset_data(
        id="lantern_lv0", name="Lantern", cost=2,
        card_class=PlayerClass.SURVIVOR, slots=[SlotType.HAND],
        traits=["item", "tool"],
    ))
    g.register_card_data(make_enemy_data(health=2))
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=3)
    g.card_registry.register_class(Lantern)
    return g


def _put_in_play(game):
    inv = game.state.get_investigator("inv1")
    iid = game.state.next_instance_id()
    game.state.cards_in_play[iid] = CardInstance(
        instance_id=iid, card_id="lantern_lv0",
        owner_id="inv1", controller_id="inv1",
    )
    inv.play_area.append(iid)
    impl = game.card_registry.activate_card(
        "lantern_lv0", iid, game.event_bus, chaos_bag=game.chaos_bag)
    return iid, impl


def _add_enemy(game, instance_id="enemy_1", engaged=False):
    enemy = CardInstance(
        instance_id=instance_id, card_id="test_enemy",
        owner_id="scenario", controller_id="scenario",
    )
    game.state.cards_in_play[instance_id] = enemy
    if engaged:
        game.state.get_investigator("inv1").threat_area.append(instance_id)
    else:
        game.state.locations["test_location"].enemies.append(instance_id)
    return enemy


class TestLantern:
    def test_card_registered(self, game):
        assert "lantern_lv0" in game.card_registry.registered_cards

    def test_armed_investigate_lowers_shroud(self, game):
        """武装后调查：隐蔽值4-1=3，智力3+0标记命中；未武装则失败。"""
        _, impl = _put_in_play(game)
        inv = game.state.get_investigator("inv1")

        # 未武装：3+0 < 4 失败
        inv.actions_remaining = 3
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]
        game.action_resolver.perform_action("inv1", Action.INVESTIGATE)
        assert game.skill_test_engine._last_result.success is False
        assert inv.clues == 0

        # 武装：3+0 >= 4-1=3 成功
        assert impl.activate(game.state, "inv1") is True
        inv.actions_remaining = 3
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]
        game.action_resolver.perform_action("inv1", Action.INVESTIGATE)
        result = game.skill_test_engine._last_result
        assert result.success is True
        assert result.difficulty == 3
        assert inv.clues == 1

    def test_arm_does_not_leak_to_non_investigate_test(self, game):
        """武装状态不影响非调查的智力检定（无 INVESTIGATE_ACTION_INITIATED）。"""
        from backend.models.enums import Skill
        _, impl = _put_in_play(game)
        assert impl.activate(game.state, "inv1") is True
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]
        # 直接跑一个智力(4)检定（非调查行动）：3+0 < 4 应失败
        result = game.skill_test_engine.run_test("inv1", Skill.INTELLECT, 4)
        assert result.success is False

    def test_discard_deals_1_damage(self, game):
        """丢弃提灯：对所在地点敌人造成1伤害。"""
        lantern_id, impl = _put_in_play(game)
        enemy = _add_enemy(game)
        inv = game.state.get_investigator("inv1")

        assert impl.activate_deal_damage(game.state, "inv1") is True
        assert enemy.damage == 1
        assert lantern_id not in inv.play_area
        assert "lantern_lv0" in inv.discard

    def test_discard_damage_defeats_enemy(self, game):
        """1伤害击败1血敌人：离场并入遭遇弃牌堆。"""
        _, impl = _put_in_play(game)
        game.register_card_data(make_enemy_data(id="rat", health=1))
        enemy = CardInstance(
            instance_id="rat_1", card_id="rat",
            owner_id="scenario", controller_id="scenario",
        )
        game.state.cards_in_play["rat_1"] = enemy
        game.state.locations["test_location"].enemies.append("rat_1")

        assert impl.activate_deal_damage(game.state, "inv1", "rat_1") is True
        assert game.state.get_card_instance("rat_1") is None
        assert "rat" in game.state.scenario.encounter_discard

    def test_deal_damage_fails_without_enemy(self, game):
        lantern_id, impl = _put_in_play(game)
        inv = game.state.get_investigator("inv1")
        assert impl.activate_deal_damage(game.state, "inv1") is False
        assert lantern_id in inv.play_area
