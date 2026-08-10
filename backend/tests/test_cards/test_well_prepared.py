"""Tests for Well Prepared (Level 2). (04151)

[快速]消耗准备万全：选择你控制的一张支援，本次技能检定技能值+X，
X为所选支援上对应的技能图标数量。
"""

import pytest
from backend.cards.guardian.well_prepared_lv2 import WellPrepared
from backend.engine.game import Game
from backend.models.enums import (
    ChaosTokenType, PlayerClass, Skill, SlotType,
)
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_asset_data, make_investigator_data, make_location_data,
)


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)

    inv_data = make_investigator_data(combat=3, willpower=2)
    g.register_card_data(inv_data)
    g.register_card_data(make_location_data())
    g.register_card_data(make_asset_data(
        id="well_prepared_lv2", name="Well Prepared", cost=2,
        card_class=PlayerClass.GUARDIAN, traits=["talent"],
    ))
    g.register_card_data(make_asset_data(
        id="guts_icon_asset", name="Combat Vest", cost=2,
        slots=[SlotType.BODY], traits=["item", "armor"],
        skill_icons={"combat": 2},
    ))
    g.register_card_data(make_asset_data(
        id="wild_icon_asset", name="Charm", cost=1,
        slots=[SlotType.ACCESSORY], traits=["item", "charm"],
        skill_icons={"wild": 1},
    ))

    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", g.state.get_card_data("test_location"))
    g.card_registry.register_class(WellPrepared)
    return g


def _deploy(game, card_id, instance_id):
    game.state.cards_in_play[instance_id] = CardInstance(
        instance_id=instance_id, card_id=card_id,
        owner_id="inv1", controller_id="inv1",
    )
    game.state.get_investigator("inv1").play_area.append(instance_id)
    return game.state.cards_in_play[instance_id]


def _deploy_prepared(game):
    _deploy(game, "well_prepared_lv2", "wp_1")
    game.card_registry.activate_card("well_prepared_lv2", "wp_1",
                                     game.event_bus)
    return (game.state.cards_in_play["wp_1"],
            game.card_registry.active_instances["wp_1"])


class TestWellPrepared:
    def test_boost_by_matching_icons(self, game):
        """横置后选2战斗图标支援：战斗检定 3+2=5 过难度5。"""
        wp, impl = _deploy_prepared(game)
        _deploy(game, "guts_icon_asset", "vest_1")
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]

        ok = impl.activate(game.state, "inv1", target_instance_id="vest_1")
        assert ok is True
        assert wp.exhausted is True

        result = game.skill_test_engine.run_test(
            "inv1", Skill.COMBAT, 5,
        )
        assert result.modified_skill == 5  # 3基础 + 2图标
        assert result.success is True

    def test_default_picks_most_icons_and_wild_matches(self, game):
        """默认选图标最多的支援；万能图标计入任意技能。"""
        wp, impl = _deploy_prepared(game)
        _deploy(game, "wild_icon_asset", "charm_1")  # 唯一支援：1万能
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]

        ok = impl.activate(game.state, "inv1")  # 默认选择 charm_1
        assert ok is True

        result = game.skill_test_engine.run_test(
            "inv1", Skill.WILLPOWER, 3,
        )
        assert result.modified_skill == 3  # 2基础 + 1万能
        assert result.success is True

    def test_fails_when_exhausted(self, game):
        """已横置时不能再次激活。"""
        wp, impl = _deploy_prepared(game)
        _deploy(game, "guts_icon_asset", "vest_1")

        assert impl.activate(game.state, "inv1") is True
        assert impl.activate(game.state, "inv1") is False

    def test_no_boost_without_activation(self, game):
        """未激活：检定无加值。"""
        _deploy_prepared(game)
        _deploy(game, "guts_icon_asset", "vest_1")
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]

        result = game.skill_test_engine.run_test("inv1", Skill.COMBAT, 4)
        assert result.modified_skill == 3
        assert result.success is False
