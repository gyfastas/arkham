"""Tests for Extra Ammunition (Level 1)."""

import pytest
from backend.cards.guardian.extra_ammunition_lv1 import ExtraAmmunition
from backend.engine.event_bus import EventContext
from backend.models.enums import GameEvent, SlotType
from backend.models.state import CardInstance
from backend.tests.conftest import make_asset_data, make_event_data


@pytest.fixture
def ammo_game(game):
    game.register_card_data(make_asset_data(
        id="45_automatic_lv0", name=".45 Automatic",
        slots=[SlotType.HAND], traits=["item", "weapon", "firearm"],
        uses={"ammo": 4},
    ))
    game.register_card_data(make_asset_data(
        id="machete_lv0", name="Machete",
        slots=[SlotType.HAND], traits=["item", "weapon", "melee"],
    ))
    game.register_card_data(make_event_data(
        id="extra_ammunition_lv1", name="Extra Ammunition", cost=2,
    ))

    impl = ExtraAmmunition("impl_1")
    impl.register(game.event_bus, "impl_1")
    return game


def _place(game, instance_id, card_id, uses=None, inv_id="test_investigator"):
    inst = CardInstance(
        instance_id=instance_id, card_id=card_id,
        owner_id=inv_id, controller_id=inv_id,
        uses=dict(uses or {}),
    )
    game.state.cards_in_play[instance_id] = inst
    game.state.get_investigator(inv_id).play_area.append(instance_id)
    return inst


def _play(game, **extra):
    ctx = EventContext(
        game_state=game.state, event=GameEvent.CARD_PLAYED,
        investigator_id="test_investigator",
        extra={"card_id": "extra_ammunition_lv1", **extra},
    )
    game.event_bus.emit(ctx)
    return ctx


class TestExtraAmmunition:
    def test_card_id(self):
        assert ExtraAmmunition.card_id == "extra_ammunition_lv1"

    def test_places_3_ammo_on_firearm(self, ammo_game):
        """在枪械上放置3弹药（官方为3，旧实现为2）。"""
        gun = _place(ammo_game, "gun_1", "45_automatic_lv0", uses={"ammo": 1})
        ctx = _play(ammo_game)
        assert gun.uses["ammo"] == 4
        assert ctx.extra["extra_ammunition_target"] == "gun_1"

    def test_skips_non_firearm(self, ammo_game):
        """近战武器不是枪械：默认选择会跳过它。"""
        _place(ammo_game, "machete_1", "machete_lv0")
        gun = _place(ammo_game, "gun_1", "45_automatic_lv0", uses={"ammo": 4})
        ctx = _play(ammo_game)
        assert gun.uses["ammo"] == 7
        assert ctx.extra["extra_ammunition_target"] == "gun_1"

    def test_no_firearm_no_effect(self, ammo_game):
        """场上没有枪械时不生效。"""
        _place(ammo_game, "machete_1", "machete_lv0")
        ctx = _play(ammo_game)
        assert "extra_ammunition_target" not in ctx.extra

    def test_explicit_non_firearm_target_rejected(self, ammo_game):
        """显式指定非枪械目标：不生效。"""
        machete = _place(ammo_game, "machete_1", "machete_lv0")
        ctx = _play(ammo_game, target_instance="machete_1")
        assert "extra_ammunition_target" not in ctx.extra
        assert machete.uses.get("ammo") is None

    def test_ignores_other_cards(self, ammo_game):
        gun = _place(ammo_game, "gun_1", "45_automatic_lv0", uses={"ammo": 1})
        ctx = EventContext(
            game_state=ammo_game.state, event=GameEvent.CARD_PLAYED,
            investigator_id="test_investigator",
            extra={"card_id": "dynamite_blast_lv0"},
        )
        ammo_game.event_bus.emit(ctx)
        assert gun.uses["ammo"] == 1
