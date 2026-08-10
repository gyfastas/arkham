"""Tests for Reliable (Level 1) and Telescopic Sight (Level 3). (04020/05230)

值得信赖：叠加到道具支援卡；结算其触发能力时全技能+1。
瞄准镜：叠加到2手枪械；不能攻击交战敌人；反应可瞄准连接地点非精英敌人。
"""

import pytest

from backend.cards.guardian.reliable_lv1 import Reliable
from backend.cards.guardian.telescopic_sight_lv3 import TelescopicSight
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import (
    CardType, GameEvent, PlayerClass, Skill, SlotType,
)
from backend.models.state import CardData, CardInstance
from backend.tests.conftest import (
    make_asset_data, make_enemy_data, make_event_data,
    make_investigator_data, make_location_data,
)


def _equip(game, card_data, iid, inv_id="inv1", slot_used=None):
    game.register_card_data(card_data)
    inst = CardInstance(
        instance_id=iid, card_id=card_data.id,
        owner_id=inv_id, controller_id=inv_id,
        slot_used=slot_used if slot_used is not None else list(card_data.slots),
    )
    game.state.cards_in_play[iid] = inst
    game.state.get_investigator(inv_id).play_area.append(iid)
    return inst


def _play_event(game, card_id, inv_id="inv1", **extra):
    ctx = EventContext(
        game_state=game.state, event=GameEvent.CARD_PLAYED,
        investigator_id=inv_id, extra={"card_id": card_id, **extra},
    )
    game.event_bus.emit(ctx)
    return ctx


class TestReliable:
    def _game(self):
        g = Game("test")
        g.chaos_bag.seed(42)
        inv_data = make_investigator_data()
        g.register_card_data(inv_data)
        loc = make_location_data()
        g.register_card_data(loc)
        g.register_card_data(make_event_data(
            id="reliable_lv1", name="Reliable", cost=1,
            card_class=PlayerClass.GUARDIAN,
        ))
        g.add_investigator("inv1", inv_data, starting_location="test_location")
        g.add_location("test_location", g.state.get_card_data("test_location"))
        g.card_registry.register_class(Reliable)
        _equip(g, make_asset_data(
            id="flashlight_x", cost=2, slots=[SlotType.HAND],
            traits=["item", "tool"],
        ), "item_1")
        return g

    def test_attach_and_boost_on_item_ability(self):
        """叠加到道具支援后：以该卡为来源的检定获得+1技能值。"""
        game = self._game()
        impl = Reliable("rel_1")
        impl.register(game.event_bus, "rel_1")

        ctx = _play_event(game, "reliable_lv1", attach_to="item_1")
        assert ctx.extra.get("reliable_attached") == "item_1"

        boost_ctx = EventContext(
            game_state=game.state, event=GameEvent.SKILL_VALUE_DETERMINED,
            investigator_id="inv1", skill_type=Skill.INTELLECT,
            amount=3, source="item_1",
        )
        game.event_bus.emit(boost_ctx)
        assert boost_ctx.amount == 4

    def test_no_boost_for_other_sources(self):
        """非被叠加卡为来源的检定不加值。"""
        game = self._game()
        impl = Reliable("rel_1")
        impl.register(game.event_bus, "rel_1")
        _play_event(game, "reliable_lv1", attach_to="item_1")

        ctx = EventContext(
            game_state=game.state, event=GameEvent.SKILL_VALUE_DETERMINED,
            investigator_id="inv1", skill_type=Skill.INTELLECT,
            amount=3, source="other_card",
        )
        game.event_bus.emit(ctx)
        assert ctx.amount == 3

    def test_attach_requires_item(self):
        """不能叠加到非道具支援。"""
        game = self._game()
        _equip(game, make_asset_data(
            id="beat_cop_x", cost=3, slots=[SlotType.ALLY], traits=["ally"],
        ), "ally_1")
        impl = Reliable("rel_1")
        impl.register(game.event_bus, "rel_1")

        ctx = _play_event(game, "reliable_lv1", attach_to="ally_1")
        assert ctx.extra.get("reliable_fizzle") is True


class TestTelescopicSight:
    def _game(self):
        g = Game("test")
        g.chaos_bag.seed(42)
        inv_data = make_investigator_data()
        g.register_card_data(inv_data)
        loc_a = make_location_data(id="loc_a", connections=["loc_b"])
        loc_b = make_location_data(id="loc_b", connections=["loc_a"])
        g.register_card_data(loc_a)
        g.register_card_data(loc_b)
        g.register_card_data(make_event_data(
            id="telescopic_sight_lv3", name="Telescopic Sight", cost=3,
            card_class=PlayerClass.GUARDIAN,
        ))
        g.register_card_data(make_enemy_data(id="ghoul", health=3))
        g.add_investigator("inv1", inv_data, starting_location="loc_a")
        g.add_location("loc_a", loc_a)
        g.add_location("loc_b", loc_b)
        g.card_registry.register_class(TelescopicSight)
        _equip(g, CardData(
            id="shotgun_x", name="Shotgun", name_cn="霰弹枪",
            type=CardType.ASSET, card_class=PlayerClass.GUARDIAN, cost=4,
            slots=[SlotType.HAND, SlotType.HAND],
            traits=["item", "weapon", "firearm"],
        ), "gun_1", slot_used=[SlotType.HAND, SlotType.HAND])
        return g

    def _spawn(self, game, iid, engaged=False, location="loc_b"):
        enemy = CardInstance(
            instance_id=iid, card_id="ghoul",
            owner_id="scenario", controller_id="scenario",
        )
        game.state.cards_in_play[iid] = enemy
        if engaged:
            game.state.get_investigator("inv1").threat_area.append(iid)
        else:
            game.state.locations[location].enemies.append(iid)
        return enemy

    def test_attach_two_hand_firearm(self):
        game = self._game()
        impl = TelescopicSight("ts_1")
        impl.register(game.event_bus, "ts_1")
        ctx = _play_event(game, "telescopic_sight_lv3", attach_to="gun_1")
        assert ctx.extra.get("telescopic_sight_attached") == "gun_1"
        record = game.state.scenario.vars["telescopic_sight"]
        assert record["asset"] == "gun_1"

    def test_cannot_attack_engaged_enemy(self):
        """用被叠加枪械攻击交战敌人：攻击被取消。"""
        game = self._game()
        impl = TelescopicSight("ts_1")
        impl.register(game.event_bus, "ts_1")
        _play_event(game, "telescopic_sight_lv3", attach_to="gun_1")
        self._spawn(game, "enemy_1", engaged=True)

        ctx = EventContext(
            game_state=game.state, event=GameEvent.FIGHT_ACTION_INITIATED,
            investigator_id="inv1", enemy_id="enemy_1", source="gun_1",
        )
        game.event_bus.emit(ctx)
        assert ctx.cancelled is True

    def test_can_attack_unengaged_enemy(self):
        """攻击未交战敌人：不取消。"""
        game = self._game()
        impl = TelescopicSight("ts_1")
        impl.register(game.event_bus, "ts_1")
        _play_event(game, "telescopic_sight_lv3", attach_to="gun_1")
        self._spawn(game, "enemy_1", engaged=False)

        ctx = EventContext(
            game_state=game.state, event=GameEvent.FIGHT_ACTION_INITIATED,
            investigator_id="inv1", enemy_id="enemy_1", source="gun_1",
        )
        game.event_bus.emit(ctx)
        assert ctx.cancelled is False

    def test_snipe_connecting_location(self):
        """反应：未交战时可瞄准连接地点非精英敌人（每场一次）。"""
        game = self._game()
        impl = TelescopicSight("ts_1")
        impl.register(game.event_bus, "ts_1")
        _play_event(game, "telescopic_sight_lv3", attach_to="gun_1")
        self._spawn(game, "enemy_1", engaged=False, location="loc_b")

        assert impl.activate_snipe(game.state, "inv1", "enemy_1") is True
        # 已消耗：不能再用
        assert impl.activate_snipe(game.state, "inv1", "enemy_1") is False

    def test_snipe_requires_unengaged(self):
        """与敌人交战时不能启动狙击反应。"""
        game = self._game()
        impl = TelescopicSight("ts_1")
        impl.register(game.event_bus, "ts_1")
        _play_event(game, "telescopic_sight_lv3", attach_to="gun_1")
        self._spawn(game, "enemy_1", engaged=True)

        assert impl.activate_snipe(game.state, "inv1", "enemy_1") is False
