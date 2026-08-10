"""Tests for Inspiring Presence (Level 0). (03228)

技能卡。如果本次技能检定成功，准备你所在地点的一张盟友支援卡，
并为其治愈1点伤害或1点恐惧。
"""

import pytest
from backend.cards.guardian.inspiring_presence_lv0 import InspiringPresence
from backend.engine.game import Game
from backend.models.enums import (
    ChaosTokenType, CardType, PlayerClass, Skill, SlotType,
)
from backend.models.state import CardData, CardInstance
from backend.tests.conftest import (
    make_asset_data, make_investigator_data, make_location_data,
    make_skill_data,
)


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)

    inv_data = make_investigator_data(combat=3)
    g.register_card_data(inv_data)
    g.register_card_data(make_location_data())
    g.register_card_data(make_skill_data(
        id="inspiring_presence_lv0", name="Inspiring Presence",
        card_class=PlayerClass.GUARDIAN,
        skill_icons={"willpower": 1, "intellect": 1, "combat": 1},
    ))
    g.register_card_data(make_asset_data(
        id="guard_dog_lv0", name="Guard Dog", cost=2,
        card_class=PlayerClass.GUARDIAN, slots=[SlotType.ALLY],
        traits=["ally", "creature"], health=3, sanity=1,
    ))

    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", g.state.get_card_data("test_location"), clues=2)
    g.card_registry.register_class(InspiringPresence)

    inv = g.state.get_investigator("inv1")
    inv.hand.append("inspiring_presence_lv0")
    return g


def _add_dog(game, exhausted=True, damage=1, horror=0):
    inv = game.state.get_investigator("inv1")
    dog = CardInstance(
        instance_id="dog_1", card_id="guard_dog_lv0",
        owner_id="inv1", controller_id="inv1", slot_used=[SlotType.ALLY],
    )
    dog.exhausted = exhausted
    dog.damage = damage
    dog.horror = horror
    game.state.cards_in_play["dog_1"] = dog
    inv.play_area.append("dog_1")
    return dog


class TestInspiringPresence:
    def test_success_readies_and_heals_ally(self, game):
        """检定成功：横置带伤的盟友被准备并治愈1点伤害。"""
        dog = _add_dog(game, exhausted=True, damage=1)
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]

        result = game.skill_test_engine.run_test(
            "inv1", Skill.COMBAT, difficulty=2,
            committed_card_ids=["inspiring_presence_lv0"],
        )
        assert result.success is True  # 3 + 1图标 + 0 = 4 vs 2
        assert dog.exhausted is False
        assert dog.damage == 0

    def test_heals_horror_when_no_damage(self, game):
        """盟友只有恐惧时治愈1点恐惧。"""
        dog = _add_dog(game, exhausted=False, damage=0, horror=1)
        game.chaos_bag.tokens = [ChaosTokenType.PLUS_1]

        game.skill_test_engine.run_test(
            "inv1", Skill.COMBAT, difficulty=2,
            committed_card_ids=["inspiring_presence_lv0"],
        )
        assert dog.horror == 0

    def test_no_effect_on_failure(self, game):
        """检定失败不触发。"""
        dog = _add_dog(game, exhausted=True, damage=1)
        game.chaos_bag.tokens = [ChaosTokenType.MINUS_3]

        result = game.skill_test_engine.run_test(
            "inv1", Skill.COMBAT, difficulty=5,
            committed_card_ids=["inspiring_presence_lv0"],
        )
        assert result.success is False
        assert dog.exhausted is True
        assert dog.damage == 1

    def test_no_ally_is_noop(self, game):
        """同地点没有盟友时不产生效果（不报错）。"""
        game.chaos_bag.tokens = [ChaosTokenType.PLUS_1]
        result = game.skill_test_engine.run_test(
            "inv1", Skill.COMBAT, difficulty=2,
            committed_card_ids=["inspiring_presence_lv0"],
        )
        assert result.success is True
