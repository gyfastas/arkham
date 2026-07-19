"""Tests for enemy keyword derivation and scenario chaos token effects."""

import pytest

from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import ChaosTokenType, GameEvent, Skill
from backend.models.state import CardInstance
from backend.scenarios.official_core import (
    ScenarioController,
    _derive_enemy_keywords,
    is_elite_enemy,
)
from backend.tests.conftest import (
    make_enemy_data,
    make_investigator_data,
    make_location_data,
)


class TestEnemyKeywords:
    def test_derive_from_chinese_traits_and_text(self):
        rec = {"traits": ["類人", "怪物", "食屍鬼", "精英"], "text": "獵手。"}
        kws = _derive_enemy_keywords(rec)
        assert "ghoul" in kws
        assert "monster" in kws
        assert "humanoid" in kws
        assert "elite" in kws
        assert "hunter" in kws

    def test_no_keywords_for_plain_enemy(self):
        rec = {"traits": ["生物"], "text": ""}
        kws = _derive_enemy_keywords(rec)
        assert "hunter" not in kws
        assert "elite" not in kws

    def test_is_elite_enemy(self):
        cd = make_enemy_data()
        cd.traits = ["精英"]
        assert is_elite_enemy(cd) is True
        cd.traits = ["怪物"]
        cd.keywords = []
        assert is_elite_enemy(cd) is False
        cd.keywords = ["elite"]
        assert is_elite_enemy(cd) is True


def _make_game(scenario_id="the_gathering"):
    g = Game(scenario_id)
    inv_data = make_investigator_data()
    g.register_card_data(inv_data)
    loc_data = make_location_data(clue_value=3, connections=[])
    g.register_card_data(loc_data)
    g.add_investigator("player", inv_data, starting_location="test_location")
    g.add_location("test_location", loc_data, clues=3)
    g.setup()
    ctrl = ScenarioController(g, action_log=[])
    ctrl.attach()
    return g, ctrl


def _add_enemy(game, instance_id, card_id, keywords, location="test_location", engaged=False):
    cd = make_enemy_data(id=card_id)
    cd.keywords = keywords
    game.register_card_data(cd)
    enemy = CardInstance(
        instance_id=instance_id, card_id=card_id,
        owner_id="scenario", controller_id="scenario",
    )
    game.state.cards_in_play[instance_id] = enemy
    if engaged:
        game.state.get_investigator("player").threat_area.append(instance_id)
    else:
        game.state.locations[location].enemies.append(instance_id)
    return enemy


def _token(game, token, inv_id="player"):
    ctx = EventContext(
        game_state=game.state, event=GameEvent.CHAOS_TOKEN_RESOLVED,
        investigator_id=inv_id, chaos_token=token, amount=0,
    )
    game.event_bus.emit(ctx)
    return ctx


class TestGatheringTokens:
    def test_skull_minus_ghouls_at_location(self):
        g, _ = _make_game("the_gathering")
        _add_enemy(g, "e1", "ghoul_minion", ["ghoul"])
        _add_enemy(g, "e2", "ghoul_priest", ["ghoul", "elite"], engaged=True)
        _add_enemy(g, "e3", "swarm_of_rats", ["monster"])

        ctx = _token(g, ChaosTokenType.SKULL)
        assert ctx.amount == -2  # 2 ghouls (rats 不算)

    def test_skull_zero_with_no_ghouls(self):
        g, _ = _make_game("the_gathering")
        ctx = _token(g, ChaosTokenType.SKULL)
        assert ctx.amount == 0

    def test_cultist_minus_one_and_horror_on_fail(self):
        g, _ = _make_game("the_gathering")
        inv = g.state.get_investigator("player")
        inv.horror = 0

        ctx = _token(g, ChaosTokenType.CULTIST)
        assert ctx.amount == -1

        # 失败 → 1 恐惧
        fail_ctx = EventContext(
            game_state=g.state, event=GameEvent.SKILL_TEST_FAILED,
            investigator_id="player", success=False,
        )
        g.event_bus.emit(fail_ctx)
        assert inv.horror == 1

    def test_tablet_minus_two_damage_with_ghoul(self):
        g, _ = _make_game("the_gathering")
        inv = g.state.get_investigator("player")
        inv.damage = 0

        # 无食屍鬼：只 -2 无伤害
        ctx = _token(g, ChaosTokenType.TABLET)
        assert ctx.amount == -2
        assert inv.damage == 0

        # 有食屍鬼：-2 且受1伤害
        _add_enemy(g, "e1", "ghoul_minion", ["ghoul"])
        ctx = _token(g, ChaosTokenType.TABLET)
        assert ctx.amount == -2
        assert inv.damage == 1


class TestMidnightMasksTokens:
    def test_skull_minus_max_cultist_doom(self):
        g, _ = _make_game("the_midnight_masks")
        e1 = _add_enemy(g, "e1", "acolyte", ["cultist"])
        e1.doom = 2
        _add_enemy(g, "e2", "hunting_nightgaunt", ["monster"])

        ctx = _token(g, ChaosTokenType.SKULL)
        assert ctx.amount == -2

    def test_cultist_places_doom_on_nearest(self):
        g, _ = _make_game("the_midnight_masks")
        e1 = _add_enemy(g, "e1", "acolyte", ["cultist"], engaged=True)
        assert e1.doom == 0

        ctx = _token(g, ChaosTokenType.CULTIST)
        assert ctx.amount == -2
        assert e1.doom == 1

    def test_tablet_places_clue_on_fail(self):
        g, _ = _make_game("the_midnight_masks")
        inv = g.state.get_investigator("player")
        inv.clues = 2
        loc = g.state.locations["test_location"]
        loc.clues = 3

        ctx = _token(g, ChaosTokenType.TABLET)
        assert ctx.amount == -3

        fail_ctx = EventContext(
            game_state=g.state, event=GameEvent.SKILL_TEST_FAILED,
            investigator_id="player", success=False,
        )
        g.event_bus.emit(fail_ctx)
        assert inv.clues == 1
        assert loc.clues == 4


class TestDevourerTokens:
    def test_skull_minus_monsters(self):
        g, _ = _make_game("the_devourer_below")
        _add_enemy(g, "e1", "flesh_eater", ["monster", "ghoul"])
        _add_enemy(g, "e2", "hunting_nightgaunt", ["monster"], engaged=True)
        _add_enemy(g, "e3", "acolyte", ["cultist"])

        ctx = _token(g, ChaosTokenType.SKULL)
        assert ctx.amount == -2

    def test_elder_thing_minus_five_redraw_with_ancient_one(self):
        g, _ = _make_game("the_devourer_below")
        g.chaos_bag.tokens = [ChaosTokenType.MINUS_3]
        _add_enemy(g, "e1", "um_rdhoth", ["ancient_one", "elite"])

        ctx = _token(g, ChaosTokenType.ELDER_THING)
        # -5 + 古神在场再抽一个(-3)
        assert ctx.amount == -8

    def test_elder_thing_no_redraw_without_ancient_one(self):
        g, _ = _make_game("the_devourer_below")
        g.chaos_bag.tokens = [ChaosTokenType.MINUS_3]
        ctx = _token(g, ChaosTokenType.ELDER_THING)
        assert ctx.amount == -5
