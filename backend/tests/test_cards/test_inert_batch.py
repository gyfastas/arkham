"""Tests for the 64 previously-inert card implementations (2026-07-17 batch)."""

import pytest

from backend.cards.guardian.dodge_lv0 import Dodge
from backend.cards.guardian.dynamite_blast_lv0 import DynamiteBlast
from backend.cards.guardian.physical_training_lv0 import PhysicalTraining
from backend.cards.neutral.charisma_lv3 import Charisma
from backend.cards.neutral.flashlight_lv0 import Flashlight
from backend.cards.seeker.shortcut_lv0 import Shortcut
from backend.cards.survivor.lucky_lv0 import Lucky
from backend.engine.event_bus import EventContext
from backend.models.enums import ChaosTokenType, GameEvent, Skill, SlotType
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_asset_data,
    make_enemy_data,
    make_investigator_data,
    make_location_data,
)


def _emit(game, event, inv_id="test_investigator", **kwargs):
    ctx = EventContext(
        game_state=game.state, event=event, investigator_id=inv_id, **kwargs
    )
    game.event_bus.emit(ctx)
    return ctx


def _register(game, impl_cls, instance_id="impl_1"):
    impl = impl_cls(instance_id)
    impl.register(game.event_bus, instance_id)
    return impl


def _play(game, card_id, inv_id="test_investigator", **extra):
    return _emit(game, GameEvent.CARD_PLAYED, inv_id, extra={"card_id": card_id, **extra})


def _add_enemy(game, instance_id, engaged=False, location="test_location"):
    game.register_card_data(make_enemy_data())
    enemy = CardInstance(
        instance_id=instance_id, card_id="test_enemy",
        owner_id="scenario", controller_id="scenario",
    )
    game.state.cards_in_play[instance_id] = enemy
    if engaged:
        game.state.get_investigator("test_investigator").threat_area.append(instance_id)
    else:
        game.state.locations[location].enemies.append(instance_id)
    return enemy


class TestShortcut:
    def test_moves_to_connected_location(self, game):
        """Playing Shortcut sets pending_choice; move happens on resolve."""
        _register(game, Shortcut)
        loc_b = make_location_data(id="loc_b", connections=["test_location"])
        game.register_card_data(loc_b)
        game.add_location("loc_b", loc_b)
        game.state.locations["test_location"].card_data.connections = ["loc_b"]

        inv = game.state.get_investigator("test_investigator")
        ctx = _play(game, "shortcut_lv0")
        # No immediate move: player picks the destination via pending_choice
        assert inv.location_id == "test_location"
        assert ctx.extra["shortcut_pending"] is True
        pc = game.state.scenario.vars.get("pending_choice")
        assert pc is not None and pc["kind"] == "shortcut_move"
        assert [o["id"] for o in pc["options"]] == ["loc_b"]


class TestDodge:
    def test_cancels_enemy_attack_from_hand(self, game):
        _register(game, Dodge)
        inv = game.state.get_investigator("test_investigator")
        inv.hand = ["dodge_lv0"]
        inv.resources = 1

        ctx = _emit(game, GameEvent.ENEMY_ATTACKS, enemy_id="e1")
        assert ctx.cancelled is True
        assert "dodge_lv0" in inv.discard
        assert inv.resources == 0

    def test_no_dodge_in_hand_no_cancel(self, game):
        _register(game, Dodge)
        inv = game.state.get_investigator("test_investigator")
        inv.hand = []
        ctx = _emit(game, GameEvent.ENEMY_ATTACKS, enemy_id="e1")
        assert ctx.cancelled is False


class TestLucky:
    def test_flips_failure_to_success(self, game):
        _register(game, Lucky)
        inv = game.state.get_investigator("test_investigator")
        inv.hand = ["lucky_lv0"]
        inv.resources = 1

        ctx = _emit(game, GameEvent.SKILL_TEST_FAILED, success=False)
        assert ctx.success is True
        assert "lucky_lv0" in inv.discard


class TestPhysicalTraining:
    def test_spend_boosts_skill(self, game):
        inv = game.state.get_investigator("test_investigator")
        impl = _register(game, PhysicalTraining, "pt_1")
        pt = CardInstance(
            instance_id="pt_1", card_id="physical_training_lv0",
            owner_id="test_investigator", controller_id="test_investigator",
        )
        game.state.cards_in_play["pt_1"] = pt
        inv.play_area.append("pt_1")
        inv.resources = 2

        assert impl.spend(game.state, "test_investigator", Skill.COMBAT) is True
        assert inv.resources == 1
        ctx = _emit(game, GameEvent.SKILL_VALUE_DETERMINED,
                    skill_type=Skill.COMBAT, amount=3)
        assert ctx.amount == 4
        # 一次性：再次检定不再加值
        ctx = _emit(game, GameEvent.SKILL_VALUE_DETERMINED,
                    skill_type=Skill.COMBAT, amount=3)
        assert ctx.amount == 3


class TestDynamiteBlast:
    def test_damages_everything_at_location(self, game):
        _register(game, DynamiteBlast)
        enemy = _add_enemy(game, "e1")
        inv = game.state.get_investigator("test_investigator")
        inv.damage = 0

        _play(game, "dynamite_blast_lv0")
        assert enemy.damage == 3
        assert inv.damage == 3


class TestCharisma:
    def test_ally_slot_bonus(self, game):
        _register(game, Charisma, "ch_1")
        cha = CardInstance(
            instance_id="ch_1", card_id="charisma_lv3",
            owner_id="test_investigator", controller_id="test_investigator",
        )
        game.state.cards_in_play["ch_1"] = cha
        mgr = game.state.slot_managers["test_investigator"]
        base = mgr.available(SlotType.ALLY)

        _emit(game, GameEvent.CARD_ENTERS_PLAY, target="ch_1")
        assert mgr.available(SlotType.ALLY) == base + 1
        _emit(game, GameEvent.CARD_LEAVES_PLAY, target="ch_1")
        assert mgr.available(SlotType.ALLY) == base


class TestFlashlight:
    def test_lowers_shroud_when_armed(self, game):
        inv = game.state.get_investigator("test_investigator")
        impl = _register(game, Flashlight, "fl_1")
        fl = CardInstance(
            instance_id="fl_1", card_id="flashlight_lv0",
            owner_id="test_investigator", controller_id="test_investigator",
        )
        fl.uses = {"supply": 3}
        game.state.cards_in_play["fl_1"] = fl
        inv.play_area.append("fl_1")

        assert impl.activate(game.state, "test_investigator") is True
        assert fl.uses["supply"] == 2

        ctx = _emit(game, GameEvent.SKILL_TEST_BEGINS,
                    skill_type=Skill.INTELLECT, difficulty=3)
        assert ctx.difficulty == 1
        assert ctx.extra["flashlight_lowered"] is True

