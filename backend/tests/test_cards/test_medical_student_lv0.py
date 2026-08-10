"""Tests for Medical Student (Level 0). (08083)

[反应]入场后：治愈同地点一位调查员或盟友的1伤害和1恐惧。
"""

import pytest
from backend.cards.guardian.medical_student_lv0 import MedicalStudent
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import GameEvent, PlayerClass, SlotType
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_asset_data, make_investigator_data, make_location_data,
)


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)
    inv_data = make_investigator_data()
    g.register_card_data(inv_data)
    g.register_card_data(make_location_data())
    g.register_card_data(make_asset_data(
        id="medical_student_lv0", name="Medical Student", cost=2,
        card_class=PlayerClass.GUARDIAN, slots=[SlotType.ALLY],
        traits=["ally", "miskatonic", "science"], health=1, sanity=1,
    ))
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", g.state.get_card_data("test_location"), clues=0)
    g.card_registry.register_class(MedicalStudent)

    inv = g.state.get_investigator("inv1")
    inst = CardInstance(
        instance_id="med_1", card_id="medical_student_lv0",
        owner_id="inv1", controller_id="inv1", slot_used=[SlotType.ALLY],
    )
    g.state.cards_in_play["med_1"] = inst
    inv.play_area.append("med_1")
    g.card_registry.activate_card("medical_student_lv0", "med_1", g.event_bus)
    return g


def _enters_play(game, **extra):
    ctx = EventContext(
        game_state=game.state, event=GameEvent.CARD_ENTERS_PLAY,
        investigator_id="inv1", target="med_1",
        extra={"card_id": "medical_student_lv0", **extra},
    )
    game.event_bus.emit(ctx)
    return ctx


class TestMedicalStudent:
    def test_heals_1_damage_1_horror_on_enter(self, game):
        """入场：自动治愈受伤最重的同地点调查员（自己）1伤害1恐惧。"""
        inv = game.state.get_investigator("inv1")
        inv.damage = 2
        inv.horror = 1

        ctx = _enters_play(game)
        assert inv.damage == 1
        assert inv.horror == 0
        assert ctx.extra["medical_student_healed"] == "inv1"

    def test_heal_ally_target_via_extra(self, game):
        """可指定盟友为治愈目标。"""
        ally = CardInstance(
            instance_id="ally_1", card_id="medical_student_lv0",
            owner_id="inv1", controller_id="inv1",
        )
        # 用第二张医学生当盟友靶子（有 health/sanity）
        game.state.cards_in_play["ally_1"] = ally
        game.state.get_investigator("inv1").play_area.append("ally_1")
        ally.damage = 1
        ally.horror = 1

        ctx = _enters_play(game, heal_target="ally_1")
        assert ally.damage == 0 and ally.horror == 0
        assert ctx.extra["medical_student_healed"] == "ally_1"

    def test_no_heal_when_nobody_hurt(self, game):
        """无人受伤：无效果。"""
        ctx = _enters_play(game)
        assert "medical_student_healed" not in ctx.extra
