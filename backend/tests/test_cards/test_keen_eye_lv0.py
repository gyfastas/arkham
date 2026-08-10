"""Tests for Keen Eye (Level 0). (07152)

[快速]花2资源：本阶段+1智力或+1战斗（可叠加）。
"""

import pytest
from backend.cards.guardian.keen_eye_lv0 import KeenEye
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import (
    ChaosTokenType, GameEvent, PlayerClass, Skill,
)
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_asset_data, make_investigator_data, make_location_data,
)


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)
    inv_data = make_investigator_data(intellect=3, combat=3)
    g.register_card_data(inv_data)
    g.register_card_data(make_location_data())
    g.register_card_data(make_asset_data(
        id="keen_eye_lv0", name="Keen Eye", cost=2,
        card_class=PlayerClass.GUARDIAN, traits=["talent"],
    ))
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", g.state.get_card_data("test_location"), clues=0)
    g.card_registry.register_class(KeenEye)

    inv = g.state.get_investigator("inv1")
    inst = CardInstance(
        instance_id="keen_1", card_id="keen_eye_lv0",
        owner_id="inv1", controller_id="inv1",
    )
    g.state.cards_in_play["keen_1"] = inst
    inv.play_area.append("keen_1")
    inv.resources = 6
    impl = g.card_registry.activate_card("keen_eye_lv0", "keen_1", g.event_bus)
    return g, impl


class TestKeenEye:
    def test_spend_boosts_skill_for_phase(self, game):
        """花2资源：本阶段战斗+1。"""
        g, impl = game
        inv = g.state.get_investigator("inv1")
        assert impl.spend_combat(g.state, "inv1") is True
        assert inv.resources == 4

        bonuses = g.preview_skill_bonuses("inv1")
        assert bonuses.get("combat") == 1
        assert "intellect" not in bonuses

    def test_stacks_and_expires_at_phase_end(self, game):
        """两次支付叠加+2；阶段结束后清除。"""
        g, impl = game
        inv = g.state.get_investigator("inv1")
        assert impl.spend_intellect(g.state, "inv1") is True
        assert impl.spend_intellect(g.state, "inv1") is True
        assert inv.resources == 2
        assert g.preview_skill_bonuses("inv1").get("intellect") == 2

        g.event_bus.emit(EventContext(
            game_state=g.state, event=GameEvent.INVESTIGATION_PHASE_ENDS,
        ))
        assert g.preview_skill_bonuses("inv1") == {}

    def test_requires_resources(self, game):
        """资源不足2：无法支付。"""
        g, impl = game
        g.state.get_investigator("inv1").resources = 1
        assert impl.spend_combat(g.state, "inv1") is False
