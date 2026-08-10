"""Tests for Protective Gear (Level 2) and Quickdraw Holster (Level 4).

防护服(08095)：抽取危险诡计时对其造成1伤害1恐惧，取消显现。
快拔枪套(08089)：叠加1手枪械（不占手槽）；消耗以免行动费用其攻击。
"""

import pytest

from backend.cards.guardian.protective_gear_lv2 import ProtectiveGear
from backend.cards.guardian.quickdraw_holster_lv4 import QuickdrawHolster
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import (
    CardType, GameEvent, PlayerClass, SlotType,
)
from backend.models.state import CardData, CardInstance
from backend.tests.conftest import (
    make_investigator_data, make_location_data,
)


def _game():
    g = Game("test")
    g.chaos_bag.seed(42)
    inv_data = make_investigator_data()
    g.register_card_data(inv_data)
    loc = make_location_data()
    g.register_card_data(loc)
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", g.state.get_card_data("test_location"))
    return g


def _equip(game, card_data, iid, impl_cls):
    game.register_card_data(card_data)
    game.card_registry.register_class(impl_cls)
    inst = CardInstance(
        instance_id=iid, card_id=card_data.id,
        owner_id="inv1", controller_id="inv1",
        slot_used=list(card_data.slots),
    )
    game.state.cards_in_play[iid] = inst
    inv = game.state.get_investigator("inv1")
    inv.play_area.append(iid)
    slot_mgr = game.slot_managers.get("inv1")
    if slot_mgr is not None and card_data.slots:
        slot_mgr.occupy(iid, card_data.slots, card_data.traits)
    impl = game.card_registry.activate_card(
        card_data.id, iid, game.event_bus, chaos_bag=game.chaos_bag)
    return inst, impl


def _firearm(card_id="colt"):
    return CardData(
        id=card_id, name=card_id, name_cn=card_id, type=CardType.ASSET,
        card_class=PlayerClass.GUARDIAN, cost=2, slots=[SlotType.HAND],
        traits=["item", "weapon", "firearm"],
    )


class TestProtectiveGear:
    def _equip_gear(self, game):
        return _equip(game, CardData(
            id="protective_gear_lv2", name="Protective Gear", name_cn="防护服",
            type=CardType.ASSET, card_class=PlayerClass.GUARDIAN, cost=4,
            slots=[SlotType.BODY], health=3, sanity=3,
            traits=["item", "armor"],
        ), "gear_1", ProtectiveGear)

    def _draw(self, game, card_id):
        ctx = EventContext(
            game_state=game.state, event=GameEvent.ENCOUNTER_CARD_DRAWN,
            investigator_id="inv1", extra={"card_id": card_id},
        )
        game.event_bus.emit(ctx)
        return ctx

    def test_cancel_hazard_treachery(self):
        """抽取危险诡计：防护服承受1伤害1恐惧，显现被取消。"""
        game = _game()
        inst, _ = self._equip_gear(game)
        game.register_card_data(CardData(
            id="frostbite", name="Frostbite", name_cn="冻伤",
            type=CardType.TREACHERY, card_class=PlayerClass.NEUTRAL,
            traits=["hazard"],
        ))

        ctx = self._draw(game, "frostbite")
        assert inst.damage == 1
        assert inst.horror == 1
        assert game.state.scenario.vars.get("cancelled_encounter") == "frostbite"
        assert ctx.extra.get("protective_gear_cancelled") == "frostbite"

    def test_ignores_non_hazard(self):
        """非危险特质的诡计不触发。"""
        game = _game()
        inst, _ = self._equip_gear(game)
        game.register_card_data(CardData(
            id="frozen_fear", name="F", name_cn="F",
            type=CardType.TREACHERY, card_class=PlayerClass.NEUTRAL,
            traits=["terror"],
        ))

        self._draw(game, "frozen_fear")
        assert inst.damage == 0 and inst.horror == 0
        assert "cancelled_encounter" not in game.state.scenario.vars

    def test_defeated_at_durability_limit(self):
        """第三次触发：耐久耗尽，防护服被击败离场。"""
        game = _game()
        inst, _ = self._equip_gear(game)
        game.register_card_data(CardData(
            id="frostbite", name="Frostbite", name_cn="冻伤",
            type=CardType.TREACHERY, card_class=PlayerClass.NEUTRAL,
            traits=["hazard"],
        ))
        inv = game.state.get_investigator("inv1")
        for _ in range(3):
            self._draw(game, "frostbite")
        assert "gear_1" not in inv.play_area
        assert game.state.get_card_instance("gear_1") is None


class TestQuickdrawHolster:
    def _equip_holster(self, game):
        return _equip(game, CardData(
            id="quickdraw_holster_lv4", name="Quickdraw Holster",
            name_cn="快拔枪套", type=CardType.ASSET,
            card_class=PlayerClass.GUARDIAN, cost=4, slots=[SlotType.BODY],
            traits=["item", "tool", "illicit"],
        ), "holster_1", QuickdrawHolster)

    def test_attach_frees_hand_slot(self):
        """叠加1手枪械：其手部槽位被释放。"""
        game = _game()
        _, impl = self._equip_holster(game)
        _equip(game, _firearm(), "gun_1", QuickdrawHolster)
        slot_mgr = game.slot_managers["inv1"]
        assert slot_mgr.count_used(SlotType.HAND) == 1

        assert impl.activate_attach(game.state, "inv1", "gun_1") is True
        gun = game.state.get_card_instance("gun_1")
        assert gun.attached_to == "holster_1"
        assert slot_mgr.count_used(SlotType.HAND) == 0

    def test_switch_restores_old_firearm_slots(self):
        """交换：旧枪械重新占用手槽，新枪械不占。"""
        game = _game()
        _, impl = self._equip_holster(game)
        _equip(game, _firearm("colt"), "gun_1", QuickdrawHolster)
        _equip(game, _firearm("derringer"), "gun_2", QuickdrawHolster)
        slot_mgr = game.slot_managers["inv1"]

        assert impl.activate_attach(game.state, "inv1", "gun_1") is True
        assert impl.activate_attach(game.state, "inv1", "gun_2") is True

        gun1 = game.state.get_card_instance("gun_1")
        gun2 = game.state.get_card_instance("gun_2")
        assert gun1.attached_to is None
        assert gun2.attached_to == "holster_1"
        # gun_2 不占手槽，gun_1 恢复占用1个
        assert slot_mgr.count_used(SlotType.HAND) == 1
        assert "gun_1" in slot_mgr.get_cards_in_slot(SlotType.HAND)

    def test_fast_fight_exhausts_and_returns_firearm(self):
        """消耗枪套：返回叠加枪械实例 id 供会话层发起免费攻击。"""
        game = _game()
        holster, impl = self._equip_holster(game)
        _equip(game, _firearm(), "gun_1", QuickdrawHolster)
        impl.activate_attach(game.state, "inv1", "gun_1")

        assert impl.activate_fast_fight(game.state, "inv1") == "gun_1"
        assert holster.exhausted is True
        # 已横置：不能再次启动
        assert impl.activate_fast_fight(game.state, "inv1") is None

    def test_attach_rejects_two_hand_firearm(self):
        """占2个手槽的枪械不能叠加。"""
        game = _game()
        _, impl = self._equip_holster(game)
        _equip(game, CardData(
            id="shotgun_x", name="S", name_cn="S", type=CardType.ASSET,
            card_class=PlayerClass.GUARDIAN, cost=4,
            slots=[SlotType.HAND, SlotType.HAND],
            traits=["item", "weapon", "firearm"],
        ), "gun_big", QuickdrawHolster)
        assert impl.activate_attach(game.state, "inv1", "gun_big") is False
