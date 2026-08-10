"""Tests for Holy Rosary (Level 2). (07220)

+1意志；[反应]诡计的意志检定成功后横置：向混乱袋加2个祝福。
"""

import pytest
from backend.cards.guardian.holy_rosary_lv2 import HolyRosary
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import (
    ChaosTokenType, GameEvent, PlayerClass, Skill, SlotType,
)
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_asset_data, make_investigator_data, make_location_data,
)


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)
    inv_data = make_investigator_data(willpower=3)
    g.register_card_data(inv_data)
    g.register_card_data(make_location_data())
    g.register_card_data(make_asset_data(
        id="holy_rosary_lv2", name="Holy Rosary", cost=2,
        card_class=PlayerClass.GUARDIAN, slots=[SlotType.ACCESSORY],
        traits=["item", "charm", "blessed"],
    ))
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", g.state.get_card_data("test_location"), clues=0)
    g.card_registry.register_class(HolyRosary)

    inv = g.state.get_investigator("inv1")
    inst = CardInstance(
        instance_id="rosary_1", card_id="holy_rosary_lv2",
        owner_id="inv1", controller_id="inv1",
        slot_used=[SlotType.ACCESSORY],
    )
    g.state.cards_in_play["rosary_1"] = inst
    inv.play_area.append("rosary_1")
    impl = g.card_registry.activate_card(
        "holy_rosary_lv2", "rosary_1", g.event_bus, chaos_bag=g.chaos_bag)
    return g, impl


class TestHolyRosary:
    def test_willpower_bonus(self, game):
        """在场时意志+1。"""
        g, _ = game
        bonuses = g.preview_skill_bonuses("inv1")
        assert bonuses.get("willpower") == 1

    def test_reaction_adds_2_bless_on_treachery_test(self, game):
        """带诡计标记的意志检定成功：横置并加2个祝福。"""
        g, _ = game
        bless_before = g.chaos_bag.tokens.count(ChaosTokenType.BLESS)
        ctx = EventContext(
            game_state=g.state, event=GameEvent.SKILL_TEST_SUCCESSFUL,
            investigator_id="inv1", skill_type=Skill.WILLPOWER,
            extra={"treachery_card_id": "some_treachery"},
        )
        g.event_bus.emit(ctx)

        assert ctx.extra["holy_rosary_bless"] == 2
        inst = g.state.get_card_instance("rosary_1")
        assert inst.exhausted is True
        assert g.chaos_bag.tokens.count(ChaosTokenType.BLESS) == bless_before + 2

    def test_no_trigger_on_plain_test(self, game):
        """非诡计检定成功不触发。"""
        g, _ = game
        ctx = EventContext(
            game_state=g.state, event=GameEvent.SKILL_TEST_SUCCESSFUL,
            investigator_id="inv1", skill_type=Skill.WILLPOWER, extra={},
        )
        g.event_bus.emit(ctx)
        assert "holy_rosary_bless" not in ctx.extra
        assert g.state.get_card_instance("rosary_1").exhausted is False

    def test_public_method_for_scenario_layer(self, game):
        """剧本/会话层可直接调用公开方法结算反应。"""
        g, impl = game
        bless_before = g.chaos_bag.tokens.count(ChaosTokenType.BLESS)
        assert impl.on_treachery_willpower_success(g.state, "inv1") is True
        assert g.chaos_bag.tokens.count(ChaosTokenType.BLESS) == bless_before + 2
        # 已横置：不能再次触发
        assert impl.on_treachery_willpower_success(g.state, "inv1") is False
