"""Tests for Sign Magick, Talisman of Protection, True Magick,
Twila Katherine Price — 支援卡批次。"""

import pytest

from backend.cards.mystic.sign_magick_lv0 import SignMagick
from backend.cards.mystic.talisman_of_protection_lv0 import TalismanOfProtection
from backend.cards.mystic.true_magick_lv5 import TrueMagick
from backend.cards.mystic.twila_katherine_price_lv3 import TwilaKatherinePrice
from backend.engine.event_bus import EventBus, EventContext
from backend.engine.slots import SlotManager
from backend.models.enums import GameEvent, SlotType
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, ScenarioState,
)
from backend.tests.conftest import make_asset_data, make_investigator_data


def _base_state():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()
    inv_data = make_investigator_data(health=5, sanity=5)
    state.card_database[inv_data.id] = inv_data
    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1")
    state.investigators["inv1"] = inv
    return state, bus, inv


def _put_in_play(state, inv, card_id, instance_id="inst1", **kwargs):
    state.card_database[card_id] = make_asset_data(id=card_id, **kwargs)
    inst = CardInstance(
        instance_id=instance_id, card_id=card_id,
        owner_id="inv1", controller_id="inv1",
    )
    state.cards_in_play[instance_id] = inst
    inv.play_area.append(instance_id)
    return inst


def _emit(bus, state, event, **kwargs):
    ctx = EventContext(game_state=state, event=event, investigator_id="inv1", **kwargs)
    bus.emit(ctx)
    return ctx


class TestSignMagick:
    CID = "sign_magick_lv0"

    def test_grants_spell_only_arcane_slot(self):
        state, bus, inv = _base_state()
        mgr = SlotManager()
        state.slot_managers = {"inv1": mgr}
        # 两个奥秘槽已满
        mgr.occupy("a1", [SlotType.ARCANE], ["spell"])
        mgr.occupy("a2", [SlotType.ARCANE], ["spell"])
        assert mgr.can_play_card([SlotType.ARCANE], ["spell"]) is False

        inst = _put_in_play(state, inv, self.CID)
        impl = SignMagick("inst1")
        impl.register(bus, "inst1")
        _emit(bus, state, GameEvent.CARD_ENTERS_PLAY, target="inst1",
              extra={"card_id": self.CID})

        # 法术/仪式可使用额外槽位
        assert mgr.can_play_card([SlotType.ARCANE], ["spell"]) is True
        assert mgr.can_play_card([SlotType.ARCANE], ["ritual"]) is True
        # 只有1个额外槽：第3张法术入场后，第4张法术仍不可用
        mgr.occupy("a3", [SlotType.ARCANE], ["spell"])
        assert mgr.can_play_card([SlotType.ARCANE], ["spell"]) is False

        # 离场收回
        mgr.vacate("a3")
        _emit(bus, state, GameEvent.CARD_LEAVES_PLAY, target="inst1",
              extra={"card_id": self.CID})
        assert mgr.can_play_card([SlotType.ARCANE], ["spell"]) is False


class TestTalismanOfProtection:
    CID = "talisman_of_protection_lv0"

    def _setup(self):
        state, bus, inv = _base_state()
        inst = _put_in_play(state, inv, self.CID)
        impl = TalismanOfProtection("inst1")
        impl.register(bus, "inst1")
        return state, bus, inv, inst, impl

    def test_cancel_2_damage_when_would_defeat(self):
        state, bus, inv, inst, impl = self._setup()
        inv.damage = 4  # 生命5：再受2伤即被击败
        ctx = _emit(bus, state, GameEvent.DAMAGE_ASSIGNED, amount=2)
        assert ctx.amount == 0  # 取消2点
        assert ctx.extra["talisman_of_protection_cancelled"] == 2
        assert "inst1" not in state.cards_in_play
        assert self.CID in inv.discard

    def test_cancel_caps_at_2(self):
        state, bus, inv, inst, impl = self._setup()
        inv.horror = 4  # 理智5：再受4恐即被击败
        ctx = _emit(bus, state, GameEvent.HORROR_ASSIGNED, amount=4)
        assert ctx.amount == 2  # 只取消2点

    def test_no_trigger_when_not_lethal(self):
        state, bus, inv, inst, impl = self._setup()
        ctx = _emit(bus, state, GameEvent.DAMAGE_ASSIGNED, amount=1)
        assert ctx.amount == 1  # 不取消
        assert "inst1" in state.cards_in_play


class TestTrueMagick:
    CID = "true_magick_lv5"

    def test_replenish_charge_each_round(self):
        state, bus, inv = _base_state()
        inst = _put_in_play(state, inv, self.CID)
        inst.uses = {"charges": 0}
        impl = TrueMagick("inst1")
        impl.register(bus, "inst1")
        _emit(bus, state, GameEvent.ROUND_BEGINS)
        assert inst.uses["charges"] == 1


class TestTwilaKatherinePrice:
    CID = "twila_katherine_price_lv3"

    def _setup(self):
        state, bus, inv = _base_state()
        twila = _put_in_play(state, inv, self.CID, instance_id="twila1",
                             health=1, sanity=2, traits=["ally"])
        spell = _put_in_play(state, inv, "shrivelling_lv0",
                             instance_id="spell1", traits=["spell"])
        spell.uses = {"charges": 2}
        impl = TwilaKatherinePrice("twila1")
        impl.register(bus, "twila1")
        return state, bus, inv, twila, spell, impl

    def test_trigger_places_charge_and_exhausts(self):
        state, bus, inv, twila, spell, impl = self._setup()
        assert impl.trigger(state, "inv1", "spell1") is True
        assert spell.uses["charges"] == 3
        assert twila.exhausted is True

    def test_no_trigger_when_exhausted(self):
        state, bus, inv, twila, spell, impl = self._setup()
        twila.exhausted = True
        assert impl.trigger(state, "inv1", "spell1") is False
        assert spell.uses["charges"] == 2

    def test_no_trigger_on_non_spell(self):
        state, bus, inv, twila, spell, impl = self._setup()
        tool = _put_in_play(state, inv, "tool", instance_id="tool1",
                            traits=["tool"])
        tool.uses = {"charges": 1}
        assert impl.trigger(state, "inv1", "tool1") is False
