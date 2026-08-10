"""Tests for Trish Scarborough investigator ability."""

import pytest
from backend.cards.rogue.trish_scarborough import TrishScarborough
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import ChaosTokenType, GameEvent
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_enemy_data, make_investigator_data, make_location_data,
)


@pytest.fixture
def game():
    g = Game("test_trish")
    g.chaos_bag.seed(42)

    inv_data = make_investigator_data(id="trish_scarborough", name="Trish Scarborough")
    g.register_card_data(inv_data)

    loc_data = make_location_data(id="test_location", connections=["other_location"])
    g.register_card_data(loc_data)
    other_loc = make_location_data(id="other_location", connections=["test_location"])
    g.register_card_data(other_loc)

    enemy_data = make_enemy_data()
    g.register_card_data(enemy_data)

    deck = ["card_a", "card_b", "card_c", "card_d", "card_e"] * 3
    g.add_investigator("trish", inv_data, deck=deck, starting_location="test_location")
    g.add_location("test_location", loc_data, clues=3)
    g.add_location("other_location", other_loc, clues=2)
    g.state.locations["other_location"].revealed = True

    return g


@pytest.fixture
def impl(game):
    impl = TrishScarborough("test_instance")
    impl.register(game.event_bus, "test_instance")
    return impl


def _emit(game, event, **kwargs):
    ctx = EventContext(game_state=game.state, event=event, **kwargs)
    game.event_bus.emit(ctx)
    return ctx


def _add_enemy(game, instance_id="enemy_1"):
    enemy = CardInstance(
        instance_id=instance_id, card_id="test_enemy",
        owner_id="scenario", controller_id="scenario",
    )
    game.state.cards_in_play[instance_id] = enemy
    return enemy


def _discover_clue(game, location_id="test_location"):
    """模拟引擎的调查成功：先扣线索再发 CLUE_DISCOVERED。"""
    inv = game.state.get_investigator("trish")
    loc = game.state.locations[location_id]
    loc.clues -= 1
    inv.clues += 1
    return _emit(
        game, GameEvent.CLUE_DISCOVERED,
        investigator_id="trish", location_id=location_id, amount=1,
    )


class TestTrishReaction:
    def test_pending_choice_at_enemy_location(self, game, impl):
        """在有敌人的地点发现线索：提供额外线索/自动躲避/不触发选项。"""
        inv = game.state.get_investigator("trish")
        _add_enemy(game)
        inv.threat_area.append("enemy_1")

        _discover_clue(game)
        pending = game.state.scenario.vars.get("pending_choice")
        assert pending is not None
        assert pending["kind"] == "trish_scarborough_reaction"
        option_ids = [o["id"] for o in pending["options"]]
        assert "clue" in option_ids
        assert "evade:enemy_1" in option_ids
        assert "decline" in option_ids

    def test_no_pending_without_enemy(self, game, impl):
        """无敌人的地点发现线索：不触发。"""
        _discover_clue(game)
        assert game.state.scenario.vars.get("pending_choice") is None

    def test_unengaged_enemy_at_location_counts(self, game, impl):
        """地点上未交战的敌人也算"有敌人"。"""
        _add_enemy(game)
        game.state.locations["test_location"].enemies.append("enemy_1")
        _discover_clue(game)
        assert game.state.scenario.vars.get("pending_choice") is not None

    def test_resolve_extra_clue_once_per_round(self, game, impl):
        """选择额外线索：地点-1线索、调查员+1；每轮限1次，下轮重置。"""
        inv = game.state.get_investigator("trish")
        loc = game.state.locations["test_location"]
        _add_enemy(game)
        inv.threat_area.append("enemy_1")

        _discover_clue(game)  # 3→2, inv 1
        assert impl.resolve_reaction(game.state, "trish", "clue") is True
        assert loc.clues == 1
        assert inv.clues == 2
        assert game.state.scenario.vars.get("pending_choice") is None

        # 同轮第二次发现：不再提供选择（正常发现仍生效）
        _discover_clue(game)  # 1→0, inv 3
        assert game.state.scenario.vars.get("pending_choice") is None
        assert inv.clues == 3

        # 新一轮：限次重置
        loc.clues = 2
        _emit(game, GameEvent.ROUND_BEGINS)
        _discover_clue(game)  # 2→1, inv 4
        assert game.state.scenario.vars.get("pending_choice") is not None
        assert impl.resolve_reaction(game.state, "trish", "clue") is True
        assert loc.clues == 0
        assert inv.clues == 5

    def test_resolve_auto_evade(self, game, impl):
        """选择自动躲避：敌人横置、脱离交战、留在该地点。"""
        inv = game.state.get_investigator("trish")
        loc = game.state.locations["test_location"]
        enemy = _add_enemy(game)
        inv.threat_area.append("enemy_1")

        _discover_clue(game)
        assert impl.resolve_reaction(game.state, "trish", "evade:enemy_1") is True
        assert enemy.exhausted
        assert "enemy_1" not in inv.threat_area
        assert "enemy_1" in loc.enemies

    def test_decline_does_not_use_limit(self, game, impl):
        """选择不触发：不消耗每轮限次。"""
        inv = game.state.get_investigator("trish")
        _add_enemy(game)
        inv.threat_area.append("enemy_1")

        _discover_clue(game)
        assert impl.resolve_reaction(game.state, "trish", "decline") is True
        # 再次发现：仍提供选择
        _discover_clue(game)
        assert game.state.scenario.vars.get("pending_choice") is not None

    def test_other_investigator_not_triggered(self, game, impl):
        """其他调查员发现线索不触发。"""
        _add_enemy(game)
        game.state.locations["test_location"].enemies.append("enemy_1")
        _emit(
            game, GameEvent.CLUE_DISCOVERED,
            investigator_id="someone_else", location_id="test_location", amount=1,
        )
        assert game.state.scenario.vars.get("pending_choice") is None


class TestTrishElderSign:
    def test_elder_sign_plus_two(self, game, impl):
        """远古印记：+2。"""
        ctx = _emit(
            game, GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="trish", chaos_token=ChaosTokenType.ELDER_SIGN,
        )
        assert ctx.amount == 2
        _emit(game, GameEvent.SKILL_TEST_ENDS, investigator_id="trish")

    def test_non_elder_sign_no_bonus(self, game, impl):
        ctx = _emit(
            game, GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="trish", chaos_token=ChaosTokenType.SKULL, amount=-2,
        )
        assert ctx.amount == -2

    def test_elder_sign_redirect_investigation(self, game, impl):
        """调查检定中远古印记：线索改从预设的已揭示地点发现。"""
        inv = game.state.get_investigator("trish")
        own = game.state.locations["test_location"]
        target = game.state.locations["other_location"]

        assert impl.choose_elder_sign_location(
            game.state, "trish", "other_location") is True

        _emit(game, GameEvent.INVESTIGATE_ACTION_INITIATED, investigator_id="trish")
        ctx = _emit(
            game, GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="trish", chaos_token=ChaosTokenType.ELDER_SIGN,
        )
        assert ctx.amount == 2

        # 模拟引擎 on_success：先从当前地点扣线索，再发事件
        own.clues -= 1
        inv.clues += 1
        clue_ctx = _emit(
            game, GameEvent.CLUE_DISCOVERED,
            investigator_id="trish", location_id="test_location", amount=1,
        )
        # 线索改道：当前地点退回，目标地点扣减；事件地点被改写
        assert own.clues == 3
        assert target.clues == 1
        assert clue_ctx.location_id == "other_location"
        _emit(game, GameEvent.SKILL_TEST_ENDS, investigator_id="trish")

    def test_redirect_requires_revealed_location(self, game, impl):
        """未揭示地点不能设为改道目标。"""
        game.state.locations["other_location"].revealed = False
        assert impl.choose_elder_sign_location(
            game.state, "trish", "other_location") is False

    def test_redirect_not_armed_outside_investigation(self, game, impl):
        """非调查检定的远古印记不改道。"""
        inv = game.state.get_investigator("trish")
        own = game.state.locations["test_location"]
        target = game.state.locations["other_location"]

        impl.choose_elder_sign_location(game.state, "trish", "other_location")
        _emit(
            game, GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="trish", chaos_token=ChaosTokenType.ELDER_SIGN,
        )
        own.clues -= 1
        inv.clues += 1
        clue_ctx = _emit(
            game, GameEvent.CLUE_DISCOVERED,
            investigator_id="trish", location_id="test_location", amount=1,
        )
        assert own.clues == 2
        assert target.clues == 2
        assert clue_ctx.location_id == "test_location"
        _emit(game, GameEvent.SKILL_TEST_ENDS, investigator_id="trish")
