"""Tests for Path to Carcosa scenario chaos token effects (both difficulty sides)."""

from backend.engine.event_bus import EventContext
from backend.models.enums import ChaosTokenType, GameEvent
from backend.tests.test_dunwich_tokens import _fail, _succeed
from backend.tests.test_scenario_tokens import _add_enemy, _make_game, _token


def _mk(scenario_id, hard=False):
    g, ctrl = _make_game(scenario_id)
    g.state.scenario.vars["difficulty"] = "hard" if hard else "standard"
    return g, ctrl


class TestCurtainCallTokens:
    def test_skull_easy_scales_with_horror(self):
        g, _ = _mk("curtain_call")
        inv = g.state.get_investigator("player")
        inv.horror = 0
        assert _token(g, ChaosTokenType.SKULL).amount == -1
        inv.horror = 3
        assert _token(g, ChaosTokenType.SKULL).amount == -3

    def test_skull_hard_is_horror_min_1(self):
        g, _ = _mk("curtain_call", hard=True)
        inv = g.state.get_investigator("player")
        inv.horror = 0
        assert _token(g, ChaosTokenType.SKULL).amount == -1
        inv.horror = 4
        assert _token(g, ChaosTokenType.SKULL).amount == -4

    def test_symbol_places_or_takes_horror(self):
        g, _ = _mk("curtain_call")
        loc = g.state.get_location("test_location")
        loc.horror = 0
        inv = g.state.get_investigator("player")
        h0 = inv.horror
        ctx = _token(g, ChaosTokenType.CULTIST)
        assert ctx.amount == -4
        assert loc.horror == 1 and inv.horror == h0  # 地点无恐惧→放置
        ctx = _token(g, ChaosTokenType.TABLET)
        assert inv.horror == h0 + 1  # 地点有恐惧→调查员受1
        # 困难面 -5
        g2, _ = _mk("curtain_call", hard=True)
        assert _token(g2, ChaosTokenType.ELDER_THING).amount == -5


class TestTheLastKingTokens:
    def test_cultist_fail_vs_unconditional(self):
        g, _ = _mk("the_last_king")
        inv = g.state.get_investigator("player")
        inv.clues = 2
        loc = g.state.get_location("test_location")
        loc.clues = 0
        ctx = _token(g, ChaosTokenType.CULTIST)
        assert ctx.amount == -2
        assert inv.clues == 2  # 标准面失败才放
        _fail(g)
        assert inv.clues == 1 and loc.clues == 1

        g2, _ = _mk("the_last_king", hard=True)
        inv2 = g2.state.get_investigator("player")
        inv2.clues = 2
        ctx = _token(g2, ChaosTokenType.CULTIST)
        assert ctx.amount == -3
        assert inv2.clues == 1  # 困难面立即放置

    def test_skull_fail_dooms_possessed(self):
        g, _ = _mk("the_last_king")
        e = _add_enemy(g, "e1", "possessed_guest", ["possessed"])
        g.chaos_bag.tokens = [ChaosTokenType.ZERO]
        _token(g, ChaosTokenType.SKULL)
        _fail(g)
        assert e.doom == 1

    def test_tablet_horror_fail_vs_direct(self):
        g, _ = _mk("the_last_king")
        inv = g.state.get_investigator("player")
        _token(g, ChaosTokenType.TABLET)
        assert inv.horror == 0
        _fail(g)
        assert inv.horror == 1

    def test_elder_thing_shroud_and_hard_damage(self):
        g, _ = _mk("the_last_king")  # test_location shroud=2
        assert _token(g, ChaosTokenType.ELDER_THING).amount == -2
        g2, _ = _mk("the_last_king", hard=True)
        inv2 = g2.state.get_investigator("player")
        _token(g2, ChaosTokenType.ELDER_THING)
        _fail(g2)
        assert inv2.damage == 1


class TestEchoesOfThePastTokens:
    def test_skull_max_vs_total_doom(self):
        g, _ = _mk("echoes_of_the_past")
        e1 = _add_enemy(g, "e1", "cultist_a", ["cultist"])
        e2 = _add_enemy(g, "e2", "cultist_b", ["cultist"])
        e1.doom = 2
        e2.doom = 1
        assert _token(g, ChaosTokenType.SKULL).amount == -2  # 单个最多
        g2, _ = _mk("echoes_of_the_past", hard=True)
        f1 = _add_enemy(g2, "f1", "cultist_a", ["cultist"])
        f2 = _add_enemy(g2, "f2", "cultist_b", ["cultist"])
        f1.doom = 2
        f2.doom = 1
        assert _token(g2, ChaosTokenType.SKULL).amount == -3  # 总数

    def test_tablet_discard_on_fail_easy_direct_hard(self):
        g, _ = _mk("echoes_of_the_past")
        inv = g.state.get_investigator("player")
        inv.hand = ["a", "b"]
        _token(g, ChaosTokenType.TABLET)
        assert len(inv.hand) == 2
        _fail(g)
        assert len(inv.hand) == 1
        g2, _ = _mk("echoes_of_the_past", hard=True)
        inv2 = g2.state.get_investigator("player")
        inv2.hand = ["a", "b"]
        assert _token(g2, ChaosTokenType.TABLET).amount == -4
        assert len(inv2.hand) == 1  # 困难面直接弃


class TestUnspeakableOathTokens:
    def test_cultist_is_horror_count(self):
        g, _ = _mk("the_unspeakable_oath")
        inv = g.state.get_investigator("player")
        inv.horror = 3
        assert _token(g, ChaosTokenType.CULTIST).amount == -3

    def test_tablet_is_base_shroud(self):
        g, _ = _mk("the_unspeakable_oath")
        assert _token(g, ChaosTokenType.TABLET).amount == -2  # test_location shroud 2

    def test_elder_thing_puts_monster_under(self):
        g, _ = _mk("the_unspeakable_oath")
        g.state.scenario.vars["set_aside_monsters"] = ["some_monster"]
        ctx = _token(g, ChaosTokenType.ELDER_THING)
        assert ctx.amount == 0
        assert g.state.scenario.vars["under_scenario_deck"] == ["some_monster"]


class TestPhantomOfTruthTokens:
    def test_skull_doom_cap_easy(self):
        g, _ = _mk("a_phantom_of_truth")
        e = _add_enemy(g, "e1", "cultist_a", ["cultist"])
        e.doom = 7
        assert _token(g, ChaosTokenType.SKULL).amount == -5  # 标准上限5
        g2, _ = _mk("a_phantom_of_truth", hard=True)
        f = _add_enemy(g2, "f1", "cultist_a", ["cultist"])
        f.doom = 7
        assert _token(g2, ChaosTokenType.SKULL).amount == -7  # 困难无上限

    def test_elder_thing_lose_resources_by_margin(self):
        g, _ = _mk("a_phantom_of_truth")
        inv = g.state.get_investigator("player")
        inv.resources = 5
        ctx = _token(g, ChaosTokenType.ELDER_THING)
        assert ctx.amount == -2
        g.event_bus.emit(EventContext(
            game_state=g.state, event=GameEvent.SKILL_TEST_FAILED,
            investigator_id="player", success=False, difficulty=4, modified_skill=1,
        ))
        assert inv.resources == 2  # 差3点失去3


class TestPallidMaskTokens:
    def test_skull_distance_cap(self):
        g, _ = _mk("the_pallid_mask")
        g.state.scenario.vars["start_location"] = "test_location"
        assert _token(g, ChaosTokenType.SKULL).amount == 0  # 在起点，距离0

    def test_cultist_reduces_attack_damage(self):
        g, _ = _mk("the_pallid_mask")
        ctx = EventContext(
            game_state=g.state, event=GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="player", chaos_token=ChaosTokenType.CULTIST,
            amount=0, skill_type=__import__("backend.models.enums", fromlist=["Skill"]).Skill.COMBAT,
        )
        g.event_bus.emit(ctx)
        assert ctx.amount == -2
        # 成功 → bonus_damage -1
        sctx = EventContext(
            game_state=g.state, event=GameEvent.SKILL_TEST_SUCCESSFUL,
            investigator_id="player", success=True, extra={},
        )
        g.event_bus.emit(sctx)
        assert sctx.extra.get("bonus_damage") == -1

    def test_elder_thing_pulls_ghoul_on_fail(self):
        g, _ = _mk("the_pallid_mask")
        from backend.tests.test_difficulty_tokens import _register_enemy
        _register_enemy(g, "ghoul_x", ["ghoul"])
        g.state.scenario.encounter_deck = ["ghoul_x"]
        _token(g, ChaosTokenType.ELDER_THING)
        _fail(g)
        inv = g.state.get_investigator("player")
        assert any(
            g.state.get_card_instance(iid).card_id == "ghoul_x"
            for iid in inv.threat_area
        )


class TestBlackStarsRiseTokens:
    def test_skull_is_agenda_doom(self):
        g, _ = _mk("black_stars_rise")
        g.state.scenario.doom_on_agenda = 3
        assert _token(g, ChaosTokenType.SKULL).amount == -3

    def test_cultist_auto_fail_near_doomed_enemy(self):
        g, _ = _mk("black_stars_rise")
        e = _add_enemy(g, "e1", "doomed_guy", ["cultist"], engaged=True)
        e.doom = 1
        g.chaos_bag.tokens = [ChaosTokenType.ZERO]
        ctx = _token(g, ChaosTokenType.CULTIST)
        assert ctx.extra.get("force_auto_fail") is True

    def test_tablet_fail_dooms_agenda(self):
        g, _ = _mk("black_stars_rise")
        g.chaos_bag.tokens = [ChaosTokenType.ZERO]
        g.state.scenario.doom_on_agenda = 0
        _token(g, ChaosTokenType.TABLET)
        _fail(g)
        assert g.state.scenario.doom_on_agenda == 1


class TestDimCarcosaTokens:
    def test_skull_easy_sanity_zero(self):
        g, _ = _mk("dim_carcosa")
        inv = g.state.get_investigator("player")
        inv.horror = 0
        assert _token(g, ChaosTokenType.SKULL).amount == -2
        inv.horror = inv.sanity  # 神智归零
        assert _token(g, ChaosTokenType.SKULL).amount == -4

    def test_skull_hard_is_horror(self):
        g, _ = _mk("dim_carcosa", hard=True)
        inv = g.state.get_investigator("player")
        inv.horror = 3
        assert _token(g, ChaosTokenType.SKULL).amount == -3

    def test_elder_thing_lose_action_vs_monster(self):
        g, _ = _mk("dim_carcosa")
        from backend.models.enums import Skill
        _add_enemy(g, "e1", "monster_x", ["monster"], engaged=True)
        inv = g.state.get_investigator("player")
        inv.actions_remaining = 3
        ctx = EventContext(
            game_state=g.state, event=GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="player", chaos_token=ChaosTokenType.ELDER_THING,
            amount=0, skill_type=Skill.COMBAT,
        )
        g.event_bus.emit(ctx)
        _fail(g)
        assert inv.actions_remaining == 2
