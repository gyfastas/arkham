"""Tests for Michael Leigh (Level 5). (08086)

+1智力/+1战斗；成功调查后放1证据（至多3）；
[反应]发起攻击时横置+花1证据：本次攻击+1伤害。
"""

import pytest
from backend.cards.guardian.michael_leigh_lv5 import MichaelLeigh
from backend.engine.game import Game
from backend.models.enums import (
    Action, ChaosTokenType, PlayerClass, SlotType,
)
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_asset_data, make_enemy_data, make_investigator_data,
    make_location_data,
)


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)
    inv_data = make_investigator_data(intellect=3, combat=3)
    g.register_card_data(inv_data)
    loc = make_location_data(shroud=2, clue_value=2)
    g.register_card_data(loc)
    g.register_card_data(make_asset_data(
        id="michael_leigh_lv5", name="Michael Leigh", cost=4,
        card_class=PlayerClass.GUARDIAN, slots=[SlotType.ALLY],
        traits=["ally", "detective"], health=3, sanity=3,
    ))
    g.register_card_data(make_enemy_data(fight=3, health=10))

    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=2)
    g.card_registry.register_class(MichaelLeigh)

    inv = g.state.get_investigator("inv1")
    inst = CardInstance(
        instance_id="ml_1", card_id="michael_leigh_lv5",
        owner_id="inv1", controller_id="inv1", slot_used=[SlotType.ALLY],
    )
    g.state.cards_in_play["ml_1"] = inst
    inv.play_area.append("ml_1")
    inv.actions_remaining = 3
    impl = g.card_registry.activate_card(
        "michael_leigh_lv5", "ml_1", g.event_bus)
    return g, impl


class TestMichaelLeigh:
    def test_skill_bonuses(self, game):
        """+1智力/+1战斗。"""
        g, _ = game
        bonuses = g.preview_skill_bonuses("inv1")
        assert bonuses.get("intellect") == 1
        assert bonuses.get("combat") == 1

    def test_evidence_on_successful_investigate(self, game):
        """成功调查后：放置1证据。"""
        g, _ = game
        g.chaos_bag.tokens = [ChaosTokenType.ZERO]
        g.action_resolver.perform_action("inv1", Action.INVESTIGATE)
        inst = g.state.get_card_instance("ml_1")
        assert inst.uses.get("evidence") == 1

    def test_spend_evidence_for_bonus_damage(self, game):
        """横置+花1证据：攻击+1伤害。"""
        g, impl = game
        inst = g.state.get_card_instance("ml_1")
        inst.uses["evidence"] = 2
        g.state.cards_in_play["enemy_1"] = CardInstance(
            instance_id="enemy_1", card_id="test_enemy",
            owner_id="scenario", controller_id="scenario",
        )
        g.state.get_investigator("inv1").threat_area.append("enemy_1")

        assert impl.activate_damage(g.state, "inv1") is True
        assert inst.exhausted is True
        assert inst.uses["evidence"] == 1

        g.chaos_bag.tokens = [ChaosTokenType.ZERO]
        g.action_resolver.perform_action(
            "inv1", Action.FIGHT, enemy_instance_id="enemy_1")
        assert g.state.get_card_instance("enemy_1").damage == 2  # 1+1

    def test_activate_requires_evidence_and_ready(self, game):
        """无证据或已横置：不可用。"""
        g, impl = game
        assert impl.activate_damage(g.state, "inv1") is False
        inst = g.state.get_card_instance("ml_1")
        inst.uses["evidence"] = 1
        inst.exhausted = True
        assert impl.activate_damage(g.state, "inv1") is False
