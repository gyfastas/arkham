"""Tests for neutral enemy weaknesses:
Tony's Quarry / Unbound Beast / Watcher from Another Dimension /
Your Worst Nightmare.
"""

import pytest

from backend.cards.neutral.tonys_quarry_lv0 import TonysQuarry
from backend.cards.neutral.unbound_beast_lv0 import UnboundBeast
from backend.cards.neutral.watcher_from_another_dimension_lv0 import (
    WatcherFromAnotherDimension,
)
from backend.cards.neutral.your_worst_nightmare_lv0 import YourWorstNightmare
from backend.engine.event_bus import EventContext
from backend.models.enums import Action, ChaosTokenType, GameEvent
from backend.models.state import CardInstance
from backend.tests.conftest import make_enemy_data, make_location_data


def _emit(game, event, inv_id="test_investigator", **kwargs):
    ctx = EventContext(
        game_state=game.state, event=event, investigator_id=inv_id, **kwargs
    )
    game.event_bus.emit(ctx)
    return ctx


def _register(game, impl_cls, instance_id="weakness_impl"):
    impl = impl_cls(instance_id)
    impl.register(game.event_bus, instance_id)
    return impl


def _draw(game, card_id, inv_id="test_investigator"):
    inv = game.state.get_investigator(inv_id)
    inv.hand.append(card_id)
    return _emit(game, GameEvent.CARD_DRAWN, inv_id, extra={"card_id": card_id})


def _three_locations(game):
    """test_location - loc_b - loc_c 链式地点。"""
    loc_b = make_location_data(id="loc_b", connections=["test_location", "loc_c"])
    loc_c = make_location_data(id="loc_c", connections=["loc_b"])
    game.register_card_data(loc_b)
    game.register_card_data(loc_c)
    game.add_location("loc_b", loc_b)
    game.add_location("loc_c", loc_c)
    game.state.locations["test_location"].card_data.connections = ["loc_b"]


class TestTonysQuarry:
    def test_spawn_at_farthest_with_doom_and_bounty(self, game):
        """抽到：生成在离承受者最远的地点，放1毁灭+1赏金。"""
        _register(game, TonysQuarry)
        _three_locations(game)

        ctx = _draw(game, "tonys_quarry_lv0")
        inv = game.state.get_investigator("test_investigator")

        inst_id = ctx.extra.get("tonys_quarry_spawned")
        assert inst_id is not None
        enemy = game.state.get_card_instance(inst_id)
        assert enemy is not None
        assert enemy.doom == 1
        assert enemy.uses.get("bounty") == 1
        assert enemy.owner_id == "test_investigator"
        assert inst_id in game.state.locations["loc_c"].enemies  # 最远地点
        assert "tonys_quarry_lv0" not in inv.hand

    def test_single_location_fallback(self, game):
        """无其他地点时生成在当前地点。"""
        _register(game, TonysQuarry)
        ctx = _draw(game, "tonys_quarry_lv0")
        inst_id = ctx.extra.get("tonys_quarry_spawned")
        assert inst_id in game.state.locations["test_location"].enemies


class TestUnboundBeast:
    def test_no_hound_set_aside(self, game):
        """场上无受召猎犬：搁置在场外，不生成。"""
        _register(game, UnboundBeast)
        inv = game.state.get_investigator("test_investigator")

        ctx = _draw(game, "unbound_beast_lv0")

        assert ctx.extra.get("unbound_beast_set_aside") is True
        assert "unbound_beast_lv0" in game.state.scenario.vars[
            "set_aside_out_of_play"]
        assert "unbound_beast_lv0" not in inv.hand
        assert inv.threat_area == []

    def test_hound_in_play_spawns_engaged(self, game):
        """场上有受召猎犬：猎犬搁置，脱缰野兽生成并与该调查员交战。"""
        _register(game, UnboundBeast)
        inv = game.state.get_investigator("test_investigator")
        hound = CardInstance(
            instance_id="hound_1", card_id="summoned_hound_lv1",
            owner_id="test_investigator", controller_id="test_investigator",
        )
        game.state.cards_in_play["hound_1"] = hound
        inv.play_area.append("hound_1")

        ctx = _draw(game, "unbound_beast_lv0")

        inst_id = ctx.extra.get("unbound_beast_spawned")
        assert inst_id is not None
        assert inst_id in inv.threat_area  # 交战
        assert game.state.get_card_instance("hound_1") is None  # 猎犬离场
        assert "summoned_hound_lv1" in game.state.scenario.vars[
            "set_aside_out_of_play"]
        assert "hound_1" not in inv.play_area


class TestWatcherFromAnotherDimension:
    def test_revelation_stays_in_hand(self, game):
        """显现：秘密加入手牌（牌留在手牌，不进威胁区）。"""
        _register(game, WatcherFromAnotherDimension)
        inv = game.state.get_investigator("test_investigator")

        ctx = _draw(game, "watcher_from_another_dimension_lv0")

        assert ctx.extra.get("watcher_added_to_hand") is True
        assert "watcher_from_another_dimension_lv0" in inv.hand
        assert inv.threat_area == []

    def test_resolve_failure_spawns_engaged(self, game):
        impl = _register(game, WatcherFromAnotherDimension)
        inv = game.state.get_investigator("test_investigator")
        inv.hand.append("watcher_from_another_dimension_lv0")

        inst_id = impl.resolve_failure(game.state, "test_investigator")

        assert inst_id is not None
        assert inst_id in inv.threat_area
        assert "watcher_from_another_dimension_lv0" not in inv.hand

    def test_resolve_success_discards(self, game):
        impl = _register(game, WatcherFromAnotherDimension)
        inv = game.state.get_investigator("test_investigator")
        inv.hand.append("watcher_from_another_dimension_lv0")

        assert impl.resolve_success(game.state, "test_investigator") is True
        assert "watcher_from_another_dimension_lv0" in inv.discard

    def test_deck_empty_attacks_from_hand(self, game):
        """牌堆耗尽时本敌人在手牌中：从手牌攻击（官方数值 3伤害/0恐惧）。"""
        impl = _register(game, WatcherFromAnotherDimension)
        inv = game.state.get_investigator("test_investigator")
        inv.hand.append("watcher_from_another_dimension_lv0")

        assert impl.on_deck_empty(game.state, "test_investigator") is True
        assert inv.damage == 3
        # 不在手牌中则不触发
        inv.hand.remove("watcher_from_another_dimension_lv0")
        assert impl.on_deck_empty(game.state, "test_investigator") is False
        assert inv.damage == 3


class TestYourWorstNightmare:
    def _spawn(self, game):
        _register(game, YourWorstNightmare)
        ctx = _draw(game, "your_worst_nightmare_lv0")
        return ctx.extra["your_worst_nightmare_spawned"]

    def test_draw_spawns_engaged_with_bearer(self, game):
        inv = game.state.get_investigator("test_investigator")
        inst_id = self._spawn(game)
        enemy = game.state.get_card_instance(inst_id)
        assert inst_id in inv.threat_area
        assert enemy.owner_id == "test_investigator"
        assert "your_worst_nightmare_lv0" not in inv.hand

    def test_bearer_cannot_attack(self, game):
        """承受者攻击它：行动被取消（不扣行动，无伤害）。"""
        game.register_card_data(make_enemy_data(
            id="your_worst_nightmare_lv0", fight=2, health=3, evade=2,
            damage=0, horror=2))
        inst_id = self._spawn(game)
        game.chaos_bag.tokens = [ChaosTokenType.PLUS_1]
        inv = game.state.get_investigator("test_investigator")
        inv.actions_remaining = 3

        ok = game.action_resolver.perform_action(
            "test_investigator", Action.FIGHT, enemy_instance_id=inst_id)

        assert ok is False  # 攻击被取消
        assert inv.actions_remaining == 3  # 未扣行动
        assert game.state.get_card_instance(inst_id).damage == 0

    def test_other_investigator_can_attack(self, game):
        """非承受者可以正常攻击并击败它。"""
        game.register_card_data(make_enemy_data(
            id="your_worst_nightmare_lv0", fight=2, health=1, evade=2,
            damage=0, horror=2))
        inst_id = self._spawn(game)
        # 第二名调查员（非承受者）
        from backend.tests.conftest import make_investigator_data
        inv2_data = make_investigator_data(id="inv2", combat=5)
        game.register_card_data(inv2_data)
        game.add_investigator("inv2", inv2_data, starting_location="test_location")
        inv2 = game.state.get_investigator("inv2")
        inv2.threat_area.append(inst_id)  # 与 inv2 交战（猎物-仅承受者仅限制生成对象）
        inv2.actions_remaining = 3
        game.chaos_bag.tokens = [ChaosTokenType.PLUS_1]

        ok = game.action_resolver.perform_action(
            "inv2", Action.FIGHT, enemy_instance_id=inst_id)

        assert ok is True
        assert game.state.get_card_instance(inst_id) is None  # 1伤害击败

    def test_bearer_cannot_damage_via_effects(self, game):
        """承受者经非攻击效果（如炸药）对其造成的伤害归零。"""
        game.register_card_data(make_enemy_data(
            id="your_worst_nightmare_lv0", fight=2, health=3, evade=2,
            damage=0, horror=2))
        inst_id = self._spawn(game)

        game.damage_engine.deal_damage_to_enemy(
            inst_id, 2, investigator_id="test_investigator")
        assert game.state.get_card_instance(inst_id).damage == 0

        game.damage_engine.deal_damage_to_enemy(
            inst_id, 1, investigator_id="other_inv")
        assert game.state.get_card_instance(inst_id).damage == 1
