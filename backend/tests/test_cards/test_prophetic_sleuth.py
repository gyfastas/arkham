"""Tests for Prophetic (Level 3) and Sleuth (Level 3). (08120/08121)

使用(2资源)，每轮开始补满；花1资源：特征匹配卡牌的检定+1技能值。
"""

import pytest

from backend.cards.guardian.prophetic_lv3 import Prophetic
from backend.cards.guardian.sleuth_lv3 import Sleuth
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import (
    CardType, ChaosTokenType, GameEvent, PlayerClass, Skill,
)
from backend.models.state import CardData, CardInstance
from backend.tests.conftest import (
    make_asset_data, make_investigator_data, make_location_data,
)


def _game(impl_cls, card_id):
    g = Game("test")
    g.chaos_bag.seed(42)
    g.chaos_bag.tokens = [ChaosTokenType.ZERO]
    inv_data = make_investigator_data(willpower=3)
    g.register_card_data(inv_data)
    loc = make_location_data()
    g.register_card_data(loc)
    # 数据 JSON 的 uses 键笔误（resourcess），入场时应归一化
    g.register_card_data(CardData(
        id=card_id, name=card_id, name_cn=card_id, type=CardType.ASSET,
        card_class=PlayerClass.GUARDIAN, cost=3, traits=["talent"],
        uses={"resourcess": 2},
    ))
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", g.state.get_card_data("test_location"))
    g.card_registry.register_class(impl_cls)

    inst = CardInstance(
        instance_id="talent_1", card_id=card_id,
        owner_id="inv1", controller_id="inv1",
    )
    inst.uses = {"resourcess": 2}
    g.state.cards_in_play["talent_1"] = inst
    g.state.get_investigator("inv1").play_area.append("talent_1")
    impl = g.card_registry.activate_card(
        card_id, "talent_1", g.event_bus, chaos_bag=g.chaos_bag)
    g.event_bus.emit(EventContext(
        game_state=g.state, event=GameEvent.CARD_ENTERS_PLAY,
        investigator_id="inv1", target="talent_1",
        extra={"card_id": card_id},
    ))
    return g, inst, impl


class TestProphetic:
    def test_uses_normalized_on_enter(self):
        """入场：resourcess 笔误键归一化为 resources 并补满。"""
        game, inst, _ = _game(Prophetic, "prophetic_lv3")
        assert inst.uses == {"resources": 2}

    def test_spend_boosts_skill_test(self):
        """花1资源：下一次检定+1技能值（3意志+1=4）。"""
        game, inst, impl = _game(Prophetic, "prophetic_lv3")
        assert impl.spend(game.state, "inv1") is True
        assert inst.uses["resources"] == 1

        result = game.skill_test_engine.run_test(
            "inv1", Skill.WILLPOWER, difficulty=4,
        )
        assert result.modified_skill == 4
        assert result.success is True

    def test_spend_trait_gate(self):
        """特征不匹配的检定拒绝支付。"""
        game, inst, impl = _game(Prophetic, "prophetic_lv3")
        game.register_card_data(CardData(
            id="machete_x", name="M", name_cn="M", type=CardType.ASSET,
            card_class=PlayerClass.GUARDIAN, traits=["item", "weapon"],
        ))
        assert impl.spend(game.state, "inv1", test_card_id="machete_x") is False
        assert inst.uses["resources"] == 2

    def test_replenish_each_round(self):
        """每轮开始补满资源。"""
        game, inst, impl = _game(Prophetic, "prophetic_lv3")
        assert impl.spend(game.state, "inv1") is True
        assert impl.spend(game.state, "inv1") is True
        assert inst.uses["resources"] == 0
        assert impl.spend(game.state, "inv1") is False  # 耗尽

        game.event_bus.emit(EventContext(
            game_state=game.state, event=GameEvent.ROUND_BEGINS,
        ))
        assert inst.uses["resources"] == 2


class TestSleuth:
    def test_spend_boosts_skill_test(self):
        """一探究竟同样：花1资源下次检定+1。"""
        game, inst, impl = _game(Sleuth, "sleuth_lv3")
        assert impl.spend(game.state, "inv1") is True

        result = game.skill_test_engine.run_test(
            "inv1", Skill.INTELLECT, difficulty=4,
        )
        assert result.modified_skill == 4

    def test_pay_for_card(self):
        """卡上资源可用于支付特征匹配卡牌的费用。"""
        game, inst, impl = _game(Sleuth, "sleuth_lv3")
        assert impl.pay_for_card(game.state, "inv1", 2) is True
        assert inst.uses["resources"] == 0
        assert impl.pay_for_card(game.state, "inv1", 1) is False
