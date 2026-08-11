"""Tests for The Forgotten Age scenario chaos token effects.

tokens_tfa 尚未接线进 official_core 的事件分发（由主代理统一接线），
因此这里的 _token/_fail/_succeed 直接调用模块函数；同时把事件发到总线，
接线后总线分发会先消费 pending key，直接调用变为幂等空操作，两种状态下测试均绿。
"""

from backend.engine.event_bus import EventContext
from backend.models.enums import CardType, ChaosTokenType, GameEvent, PlayerClass
from backend.models.state import CardData, CardInstance
from backend.scenarios import tokens_tfa
from backend.tests.conftest import make_location_data
from backend.tests.test_scenario_tokens import _add_enemy, _make_game


def _token(game, ctrl, token, inv_id="player", **ctx_kwargs):
    ctx = EventContext(
        game_state=game.state, event=GameEvent.CHAOS_TOKEN_RESOLVED,
        investigator_id=inv_id, chaos_token=token, amount=0, **ctx_kwargs,
    )
    inv = game.state.get_investigator(inv_id)
    pending = ctrl._token_pending.setdefault(inv_id, set())
    success_pending = ctrl._token_success_pending.setdefault(inv_id, set())
    assert tokens_tfa.apply_token(ctrl, ctx, inv, pending, success_pending)
    return ctx


def _fail(game, ctrl, inv_id="player", difficulty=3, modified_skill=2):
    ctx = EventContext(
        game_state=game.state, event=GameEvent.SKILL_TEST_FAILED,
        investigator_id=inv_id, success=False,
        difficulty=difficulty, modified_skill=modified_skill,
    )
    game.event_bus.emit(ctx)
    pending = ctrl._token_pending.get(inv_id)
    if pending:
        tokens_tfa.on_fail(ctrl, ctx, pending)
    return ctx


def _succeed(game, ctrl, inv_id="player", difficulty=3, modified_skill=5):
    ctx = EventContext(
        game_state=game.state, event=GameEvent.SKILL_TEST_SUCCESSFUL,
        investigator_id=inv_id, success=True,
        difficulty=difficulty, modified_skill=modified_skill,
    )
    game.event_bus.emit(ctx)
    pending = ctrl._token_success_pending.get(inv_id)
    if pending:
        tokens_tfa.on_success(ctrl, ctx, pending)
    return ctx


def _set_hard(game):
    game.state.scenario.vars["difficulty"] = "hard"


def _poison(game, inv_id="player"):
    game.state.scenario.vars.setdefault("poisoned", []).append(inv_id)


def _make_treachery(game, card_id, traits):
    cd = CardData(
        id=card_id, name=card_id, name_cn=card_id,
        type=CardType.TREACHERY, card_class=PlayerClass.NEUTRAL,
        traits=traits,
    )
    game.register_card_data(cd)
    return cd


def _add_location(game, location_id, traits=None, connections=None, clues=0):
    loc_data = make_location_data(id=location_id, connections=connections or [])
    loc_data.traits = traits or []
    game.register_card_data(loc_data)
    game.add_location(location_id, loc_data, clues=clues)
    return game.state.locations[location_id]


class TestWildsTokens:
    def test_skull_scales_with_vengeance(self):
        g, ctrl = _make_game("wilds")
        g.state.scenario.vars["vengeance"] = 2
        ctx = _token(g, ctrl, ChaosTokenType.SKULL)
        assert ctx.amount == -2

    def test_skull_hard_is_vengeance_plus_1(self):
        g, ctrl = _make_game("wilds")
        _set_hard(g)
        g.state.scenario.vars["vengeance"] = 2
        ctx = _token(g, ctrl, ChaosTokenType.SKULL)
        assert ctx.amount == -3
        # 无复仇点也有 -1
        g.state.scenario.vars["vengeance"] = 0
        ctx = _token(g, ctrl, ChaosTokenType.SKULL)
        assert ctx.amount == -1

    def test_cultist_counts_locations_standard_max5(self):
        g, ctrl = _make_game("wilds")
        for i in range(5):
            _add_location(g, f"loc{i}")
        ctx = _token(g, ctrl, ChaosTokenType.CULTIST)
        assert ctx.amount == -5  # 6 个地点，普通面封顶 5

    def test_cultist_hard_no_cap(self):
        g, ctrl = _make_game("wilds")
        _set_hard(g)
        for i in range(5):
            _add_location(g, f"loc{i}")
        ctx = _token(g, ctrl, ChaosTokenType.CULTIST)
        assert ctx.amount == -6

    def test_tablet_exploration_deck_standard_max5(self):
        g, ctrl = _make_game("wilds")
        g.state.scenario.vars["exploration_deck"] = ["a", "b", "c"]
        ctx = _token(g, ctrl, ChaosTokenType.TABLET)
        assert ctx.amount == -3
        g.state.scenario.vars["exploration_deck"] = ["a"] * 7
        ctx = _token(g, ctrl, ChaosTokenType.TABLET)
        assert ctx.amount == -5

    def test_tablet_hard_min3(self):
        g, ctrl = _make_game("wilds")
        _set_hard(g)
        g.state.scenario.vars["exploration_deck"] = ["a"]
        ctx = _token(g, ctrl, ChaosTokenType.TABLET)
        assert ctx.amount == -3
        g.state.scenario.vars["exploration_deck"] = ["a"] * 4
        ctx = _token(g, ctrl, ChaosTokenType.TABLET)
        assert ctx.amount == -4

    def test_elder_thing_standard(self):
        g, ctrl = _make_game("wilds")
        ctx = _token(g, ctrl, ChaosTokenType.ELDER_THING)
        assert ctx.amount == -2
        assert not ctx.extra.get("force_auto_fail")

    def test_elder_thing_auto_fail_when_poisoned(self):
        g, ctrl = _make_game("wilds")
        _poison(g)
        ctx = _token(g, ctrl, ChaosTokenType.ELDER_THING)
        assert ctx.amount == 0
        assert ctx.extra.get("force_auto_fail") is True

    def test_elder_thing_hard_fail_marks_poisoned(self):
        g, ctrl = _make_game("wilds")
        _set_hard(g)
        ctx = _token(g, ctrl, ChaosTokenType.ELDER_THING)
        assert ctx.amount == -3
        _fail(g, ctrl)
        assert "player" in g.state.scenario.vars["poisoned"]


class TestEztliTokens:
    def test_skull_scales_with_location_doom(self):
        g, ctrl = _make_game("eztli")
        loc = g.state.get_location("test_location")
        ctx = _token(g, ctrl, ChaosTokenType.SKULL)
        assert ctx.amount == -1
        loc.doom = 1
        ctx = _token(g, ctrl, ChaosTokenType.SKULL)
        assert ctx.amount == -3

    def test_skull_hard(self):
        g, ctrl = _make_game("eztli")
        _set_hard(g)
        loc = g.state.get_location("test_location")
        ctx = _token(g, ctrl, ChaosTokenType.SKULL)
        assert ctx.amount == -2
        loc.doom = 1
        ctx = _token(g, ctrl, ChaosTokenType.SKULL)
        assert ctx.amount == -4

    def test_cultist_tablet_count_doomed_locations_standard(self):
        g, ctrl = _make_game("eztli")
        loc2 = _add_location(g, "loc2")
        g.state.get_location("test_location").doom = 1
        loc2.doom = 2
        # 普通面：有毁灭的地点数（2）
        ctx = _token(g, ctrl, ChaosTokenType.CULTIST)
        assert ctx.amount == -2
        ctx = _token(g, ctrl, ChaosTokenType.TABLET)
        assert ctx.amount == -2

    def test_cultist_tablet_total_location_doom_hard(self):
        g, ctrl = _make_game("eztli")
        _set_hard(g)
        loc2 = _add_location(g, "loc2")
        g.state.get_location("test_location").doom = 1
        loc2.doom = 2
        # 困难面：地点毁灭总数（3）
        ctx = _token(g, ctrl, ChaosTokenType.CULTIST)
        assert ctx.amount == -3
        ctx = _token(g, ctrl, ChaosTokenType.TABLET)
        assert ctx.amount == -3

    def test_elder_thing_standard_doom_on_fail(self):
        g, ctrl = _make_game("eztli")
        g.chaos_bag.tokens = [ChaosTokenType.MINUS_2]
        loc = g.state.get_location("test_location")
        ctx = _token(g, ctrl, ChaosTokenType.ELDER_THING)
        assert ctx.amount == -2  # 基础0 + 再揭示-2
        assert loc.doom == 0
        _fail(g, ctrl)
        assert loc.doom == 1

    def test_elder_thing_hard_doom_immediate(self):
        g, ctrl = _make_game("eztli")
        _set_hard(g)
        g.chaos_bag.tokens = [ChaosTokenType.MINUS_1]
        loc = g.state.get_location("test_location")
        ctx = _token(g, ctrl, ChaosTokenType.ELDER_THING)
        assert ctx.amount == -1
        assert loc.doom == 1  # 困难面立即放置，无需失败


class TestThreadsOfFateTokens:
    def test_skull_standard_max_cultist_doom(self):
        g, ctrl = _make_game("threads_of_fate")
        e1 = _add_enemy(g, "e1", "serpent_person", ["cultist"])
        e1.doom = 2
        e2 = _add_enemy(g, "e2", "acolyte", ["cultist"])
        e2.doom = 1
        e3 = _add_enemy(g, "e3", "yig", ["monster", "ancient_one"])
        e3.doom = 5  # 非异教徒不计
        ctx = _token(g, ctrl, ChaosTokenType.SKULL)
        assert ctx.amount == -2

    def test_skull_hard_total_doom_in_play(self):
        g, ctrl = _make_game("threads_of_fate")
        _set_hard(g)
        g.state.scenario.doom_on_agenda = 1
        g.state.get_location("test_location").doom = 2
        e1 = _add_enemy(g, "e1", "serpent_person", ["cultist"])
        e1.doom = 1
        ctx = _token(g, ctrl, ChaosTokenType.SKULL)
        assert ctx.amount == -4  # 密谋1 + 地点2 + 敌人1

    def test_cultist_fail_takes_damage(self):
        g, ctrl = _make_game("threads_of_fate")
        inv = g.state.get_investigator("player")
        ctx = _token(g, ctrl, ChaosTokenType.CULTIST)
        assert ctx.amount == -2
        _fail(g, ctrl)
        assert inv.damage == 1

    def test_cultist_success_by_zero_still_takes_damage(self):
        g, ctrl = _make_game("threads_of_fate")
        inv = g.state.get_investigator("player")
        _token(g, ctrl, ChaosTokenType.CULTIST)
        # 成功但优势为 0（未达到"至少1"）→ 仍受伤害
        _succeed(g, ctrl, difficulty=3, modified_skill=3)
        assert inv.damage == 1

    def test_cultist_success_by_1_no_damage(self):
        g, ctrl = _make_game("threads_of_fate")
        inv = g.state.get_investigator("player")
        _token(g, ctrl, ChaosTokenType.CULTIST)
        _succeed(g, ctrl, difficulty=3, modified_skill=4)
        assert inv.damage == 0

    def test_cultist_hard_needs_margin_2(self):
        g, ctrl = _make_game("threads_of_fate")
        _set_hard(g)
        inv = g.state.get_investigator("player")
        _token(g, ctrl, ChaosTokenType.CULTIST)
        _succeed(g, ctrl, difficulty=3, modified_skill=4)  # 优势1 < 2 → 直接伤害
        assert inv.damage == 1
        _token(g, ctrl, ChaosTokenType.CULTIST)
        _succeed(g, ctrl, difficulty=3, modified_skill=5)  # 优势2 → 无伤害
        assert inv.damage == 1

    def test_tablet_doom_nearest_cultist_on_fail(self):
        g, ctrl = _make_game("threads_of_fate")
        e1 = _add_enemy(g, "e1", "serpent_person", ["cultist"])
        ctx = _token(g, ctrl, ChaosTokenType.TABLET)
        assert ctx.amount == -2
        _fail(g, ctrl)
        assert e1.doom == 1

    def test_tablet_success_by_zero_places_doom(self):
        g, ctrl = _make_game("threads_of_fate")
        e1 = _add_enemy(g, "e1", "serpent_person", ["cultist"])
        _token(g, ctrl, ChaosTokenType.TABLET)
        _succeed(g, ctrl, difficulty=3, modified_skill=3)
        assert e1.doom == 1

    def test_tablet_hard_each_cultist(self):
        g, ctrl = _make_game("threads_of_fate")
        _set_hard(g)
        e1 = _add_enemy(g, "e1", "serpent_person", ["cultist"])
        e2 = _add_enemy(g, "e2", "acolyte", ["cultist"], engaged=True)
        _token(g, ctrl, ChaosTokenType.TABLET)
        _fail(g, ctrl)
        assert e1.doom == 1
        assert e2.doom == 1

    def test_elder_thing_lose_clue_on_fail(self):
        g, ctrl = _make_game("threads_of_fate")
        inv = g.state.get_investigator("player")
        inv.clues = 2
        ctx = _token(g, ctrl, ChaosTokenType.ELDER_THING)
        assert ctx.amount == -2
        _fail(g, ctrl)
        assert inv.clues == 1  # 失去的线索回 token pool，不放到地点
        assert g.state.get_location("test_location").clues == 3

    def test_elder_thing_hard(self):
        g, ctrl = _make_game("threads_of_fate")
        _set_hard(g)
        inv = g.state.get_investigator("player")
        inv.clues = 1
        ctx = _token(g, ctrl, ChaosTokenType.ELDER_THING)
        assert ctx.amount == -3
        _fail(g, ctrl)
        assert inv.clues == 0


class TestBoundaryBeyondTokens:
    def test_skull_ancient_location(self):
        g, ctrl = _make_game("the_boundary_beyond")
        loc = g.state.get_location("test_location")
        ctx = _token(g, ctrl, ChaosTokenType.SKULL)
        assert ctx.amount == -1
        loc.card_data.traits = ["ancient"]
        ctx = _token(g, ctrl, ChaosTokenType.SKULL)
        assert ctx.amount == -3

    def test_skull_hard(self):
        g, ctrl = _make_game("the_boundary_beyond")
        _set_hard(g)
        loc = g.state.get_location("test_location")
        ctx = _token(g, ctrl, ChaosTokenType.SKULL)
        assert ctx.amount == -2
        loc.card_data.traits = ["ancient"]
        ctx = _token(g, ctrl, ChaosTokenType.SKULL)
        assert ctx.amount == -4

    def test_cultist_reveal_and_doom_on_fail(self):
        g, ctrl = _make_game("the_boundary_beyond")
        g.chaos_bag.tokens = [ChaosTokenType.MINUS_1]
        e1 = _add_enemy(g, "e1", "serpent_person", ["cultist"])
        ctx = _token(g, ctrl, ChaosTokenType.CULTIST)
        assert ctx.amount == -1  # 仅再揭示的数值
        _fail(g, ctrl)
        assert e1.doom == 1

    def test_cultist_hard_doom_each_on_fail(self):
        g, ctrl = _make_game("the_boundary_beyond")
        _set_hard(g)
        g.chaos_bag.tokens = [ChaosTokenType.MINUS_1]
        e1 = _add_enemy(g, "e1", "serpent_person", ["cultist"])
        e2 = _add_enemy(g, "e2", "acolyte", ["cultist"], engaged=True)
        _token(g, ctrl, ChaosTokenType.CULTIST)
        _fail(g, ctrl)
        assert e1.doom == 1
        assert e2.doom == 1

    def test_tablet_serpent_attacks_on_fail(self):
        g, ctrl = _make_game("the_boundary_beyond")
        g.chaos_bag.tokens = [ChaosTokenType.ZERO]
        inv = g.state.get_investigator("player")
        _add_enemy(g, "e1", "pit_viper", ["serpent"])  # 1伤害1恐惧
        ctx = _token(g, ctrl, ChaosTokenType.TABLET)
        assert ctx.amount == 0
        _fail(g, ctrl)
        assert inv.damage == 1
        assert inv.horror == 1

    def test_tablet_no_serpent_no_attack(self):
        g, ctrl = _make_game("the_boundary_beyond")
        g.chaos_bag.tokens = [ChaosTokenType.ZERO]
        inv = g.state.get_investigator("player")
        _token(g, ctrl, ChaosTokenType.TABLET)
        _fail(g, ctrl)
        assert inv.damage == 0
        assert inv.horror == 0

    def test_tablet_hard_each_serpent_attacks(self):
        g, ctrl = _make_game("the_boundary_beyond")
        _set_hard(g)
        g.chaos_bag.tokens = [ChaosTokenType.ZERO]
        inv = g.state.get_investigator("player")
        _add_enemy(g, "e1", "pit_viper", ["serpent"])
        _add_enemy(g, "e2", "boa", ["serpent"], engaged=True)
        _token(g, ctrl, ChaosTokenType.TABLET)
        _fail(g, ctrl)
        assert inv.damage == 2
        assert inv.horror == 2

    def test_elder_thing_clue_on_nearest_ancient_on_fail(self):
        g, ctrl = _make_game("the_boundary_beyond")
        g.state.get_location("test_location").card_data.connections = ["ancient_near"]
        near = _add_location(g, "ancient_near", traits=["ancient"], connections=["ancient_far"])
        far = _add_location(g, "ancient_far", traits=["ancient"])
        ctx = _token(g, ctrl, ChaosTokenType.ELDER_THING)
        assert ctx.amount == -4
        _fail(g, ctrl)
        assert near.clues == 1  # 最近的古代地点
        assert far.clues == 0

    def test_elder_thing_hard_places_immediately(self):
        g, ctrl = _make_game("the_boundary_beyond")
        _set_hard(g)
        near = _add_location(g, "ancient_near", traits=["ancient"])
        ctx = _token(g, ctrl, ChaosTokenType.ELDER_THING)
        assert ctx.amount == -4
        assert near.clues == 1  # 困难面立即放置


class TestHeartOfTheEldersTokens:
    def test_skull_cave_location(self):
        g, ctrl = _make_game("heart_of_the_elders")
        loc = g.state.get_location("test_location")
        ctx = _token(g, ctrl, ChaosTokenType.SKULL)
        assert ctx.amount == -1
        loc.card_data.traits = ["cave"]
        ctx = _token(g, ctrl, ChaosTokenType.SKULL)
        assert ctx.amount == -3

    def test_skull_hard(self):
        g, ctrl = _make_game("heart_of_the_elders")
        _set_hard(g)
        loc = g.state.get_location("test_location")
        ctx = _token(g, ctrl, ChaosTokenType.SKULL)
        assert ctx.amount == -2
        loc.card_data.traits = ["cave"]
        ctx = _token(g, ctrl, ChaosTokenType.SKULL)
        assert ctx.amount == -4

    def test_cultist_doom_on_location_on_fail(self):
        g, ctrl = _make_game("heart_of_the_elders")
        loc = g.state.get_location("test_location")
        ctx = _token(g, ctrl, ChaosTokenType.CULTIST)
        assert ctx.amount == -2
        _fail(g, ctrl)
        assert loc.doom == 1

    def test_cultist_hard(self):
        g, ctrl = _make_game("heart_of_the_elders")
        _set_hard(g)
        loc = g.state.get_location("test_location")
        ctx = _token(g, ctrl, ChaosTokenType.CULTIST)
        assert ctx.amount == -3
        _fail(g, ctrl)
        assert loc.doom == 1

    def test_tablet_auto_fail_when_poisoned(self):
        g, ctrl = _make_game("heart_of_the_elders")
        _poison(g)
        ctx = _token(g, ctrl, ChaosTokenType.TABLET)
        assert ctx.amount == 0
        assert ctx.extra.get("force_auto_fail") is True

    def test_tablet_standard_plain_minus2(self):
        g, ctrl = _make_game("heart_of_the_elders")
        ctx = _token(g, ctrl, ChaosTokenType.TABLET)
        assert ctx.amount == -2
        _fail(g, ctrl)
        assert "poisoned" not in g.state.scenario.vars  # 普通面无中毒效果

    def test_tablet_hard_fail_marks_poisoned(self):
        g, ctrl = _make_game("heart_of_the_elders")
        _set_hard(g)
        ctx = _token(g, ctrl, ChaosTokenType.TABLET)
        assert ctx.amount == -3
        _fail(g, ctrl)
        assert "player" in g.state.scenario.vars["poisoned"]

    def test_elder_thing_horror_on_fail(self):
        g, ctrl = _make_game("heart_of_the_elders")
        inv = g.state.get_investigator("player")
        ctx = _token(g, ctrl, ChaosTokenType.ELDER_THING)
        assert ctx.amount == -3
        _fail(g, ctrl)
        assert inv.horror == 1

    def test_elder_thing_hard(self):
        g, ctrl = _make_game("heart_of_the_elders")
        _set_hard(g)
        inv = g.state.get_investigator("player")
        ctx = _token(g, ctrl, ChaosTokenType.ELDER_THING)
        assert ctx.amount == -4
        _fail(g, ctrl)
        assert inv.horror == 1


class TestCityOfArchivesTokens:
    def test_skull_hand_size_standard(self):
        g, ctrl = _make_game("the_city_of_archives")
        inv = g.state.get_investigator("player")
        inv.hand = ["a", "b", "c", "d"]
        ctx = _token(g, ctrl, ChaosTokenType.SKULL)
        assert ctx.amount == -1
        inv.hand = ["a", "b", "c", "d", "e"]
        ctx = _token(g, ctrl, ChaosTokenType.SKULL)
        assert ctx.amount == -3

    def test_skull_hard_auto_fail_with_5_hand(self):
        g, ctrl = _make_game("the_city_of_archives")
        _set_hard(g)
        inv = g.state.get_investigator("player")
        inv.hand = ["a", "b", "c", "d"]
        ctx = _token(g, ctrl, ChaosTokenType.SKULL)
        assert ctx.amount == -2
        inv.hand = ["a", "b", "c", "d", "e"]
        ctx = _token(g, ctrl, ChaosTokenType.SKULL)
        assert ctx.amount == 0
        assert ctx.extra.get("force_auto_fail") is True

    def test_cultist_clue_to_location_on_fail(self):
        g, ctrl = _make_game("the_city_of_archives")
        inv = g.state.get_investigator("player")
        loc = g.state.get_location("test_location")
        inv.clues = 2
        loc.clues = 1
        ctx = _token(g, ctrl, ChaosTokenType.CULTIST)
        assert ctx.amount == -2
        _fail(g, ctrl)
        assert inv.clues == 1
        assert loc.clues == 2

    def test_elder_thing_same_as_cultist(self):
        g, ctrl = _make_game("the_city_of_archives")
        inv = g.state.get_investigator("player")
        inv.clues = 1
        ctx = _token(g, ctrl, ChaosTokenType.ELDER_THING)
        assert ctx.amount == -2
        _fail(g, ctrl)
        assert inv.clues == 0
        assert g.state.get_location("test_location").clues == 4

    def test_cultist_hard_places_immediately(self):
        g, ctrl = _make_game("the_city_of_archives")
        _set_hard(g)
        inv = g.state.get_investigator("player")
        loc = g.state.get_location("test_location")
        inv.clues = 2
        loc.clues = 1
        ctx = _token(g, ctrl, ChaosTokenType.CULTIST)
        assert ctx.amount == -2
        assert inv.clues == 1  # 困难面立即放置，不等失败
        assert loc.clues == 2

    def test_tablet_discard_random_on_fail(self):
        g, ctrl = _make_game("the_city_of_archives")
        inv = g.state.get_investigator("player")
        inv.hand = ["a", "b"]
        ctx = _token(g, ctrl, ChaosTokenType.TABLET)
        assert ctx.amount == -3
        _fail(g, ctrl)
        assert len(inv.hand) == 1
        assert len(inv.discard) == 1

    def test_tablet_hard_discard_by_margin(self):
        g, ctrl = _make_game("the_city_of_archives")
        _set_hard(g)
        inv = g.state.get_investigator("player")
        inv.hand = ["a", "b", "c", "d"]
        ctx = _token(g, ctrl, ChaosTokenType.TABLET)
        assert ctx.amount == -3
        _fail(g, ctrl, difficulty=5, modified_skill=2)  # 差3点 → 弃3张
        assert len(inv.hand) == 1
        assert len(inv.discard) == 3


class TestDepthsOfYothTokens:
    def test_skull_is_depth_level(self):
        g, ctrl = _make_game("the_depths_of_yoth")
        g.state.scenario.vars["depth_level"] = 2
        ctx = _token(g, ctrl, ChaosTokenType.SKULL)
        assert ctx.amount == -2
        g.state.scenario.vars["depth_level"] = 4
        ctx = _token(g, ctrl, ChaosTokenType.SKULL)
        assert ctx.amount == -4

    def test_skull_hard_fail_takes_horror(self):
        g, ctrl = _make_game("the_depths_of_yoth")
        _set_hard(g)
        inv = g.state.get_investigator("player")
        g.state.scenario.vars["depth_level"] = 3
        ctx = _token(g, ctrl, ChaosTokenType.SKULL)
        assert ctx.amount == -3
        _fail(g, ctrl)
        assert inv.horror == 1

    def test_cultist_serpents_heal_on_fail(self):
        g, ctrl = _make_game("the_depths_of_yoth")
        g.chaos_bag.tokens = [ChaosTokenType.MINUS_1]
        g.state.get_location("test_location").card_data.connections = ["loc2"]
        _add_location(g, "loc2")
        _add_location(g, "loc3")  # 不相连
        e1 = _add_enemy(g, "e1", "pit_viper", ["serpent"])
        e1.damage = 3
        e2 = _add_enemy(g, "e2", "boa", ["serpent"], location="loc2")
        e2.damage = 2
        e3 = _add_enemy(g, "e3", "anaconda", ["serpent"], location="loc3")
        e3.damage = 3
        ctx = _token(g, ctrl, ChaosTokenType.CULTIST)
        assert ctx.amount == -1  # 再揭示
        _fail(g, ctrl)
        assert e1.damage == 1  # 3 - 2
        assert e2.damage == 0  # 相连地点也治疗
        assert e3.damage == 3  # 不相连不治疗

    def test_tablet_clue_on_location_on_fail(self):
        g, ctrl = _make_game("the_depths_of_yoth")
        g.chaos_bag.tokens = [ChaosTokenType.PLUS_1]
        loc = g.state.get_location("test_location")
        loc.clues = 3
        ctx = _token(g, ctrl, ChaosTokenType.TABLET)
        assert ctx.amount == 1  # 再揭示 +1
        _fail(g, ctrl)
        assert loc.clues == 4

    def test_elder_thing_standard(self):
        g, ctrl = _make_game("the_depths_of_yoth")
        ctx = _token(g, ctrl, ChaosTokenType.ELDER_THING)
        assert ctx.amount == -2

    def test_elder_thing_hard(self):
        g, ctrl = _make_game("the_depths_of_yoth")
        _set_hard(g)
        ctx = _token(g, ctrl, ChaosTokenType.ELDER_THING)
        assert ctx.amount == -4

    def test_elder_thing_auto_fail_with_3_vengeance(self):
        g, ctrl = _make_game("the_depths_of_yoth")
        g.state.scenario.vars["vengeance"] = 3
        ctx = _token(g, ctrl, ChaosTokenType.ELDER_THING)
        assert ctx.amount == 0
        assert ctx.extra.get("force_auto_fail") is True


class TestShatteredAeonsTokens:
    def _add_relic(self, game, inv):
        cd = CardData(
            id="relic_of_ages_a", name="Relic of Ages", name_cn="古代遗物",
            type=CardType.ASSET, card_class=PlayerClass.NEUTRAL,
            traits=["item", "relic"],
        )
        game.register_card_data(cd)
        inst = CardInstance(
            instance_id="relic1", card_id="relic_of_ages_a",
            owner_id="player", controller_id="player",
        )
        game.state.cards_in_play["relic1"] = inst
        inv.play_area.append("relic1")
        return inst

    def test_skull_standard(self):
        g, ctrl = _make_game("shattered_aeons")
        ctx = _token(g, ctrl, ChaosTokenType.SKULL)
        assert ctx.amount == -2

    def test_skull_relic_at_location(self):
        g, ctrl = _make_game("shattered_aeons")
        inv = g.state.get_investigator("player")
        self._add_relic(g, inv)
        ctx = _token(g, ctrl, ChaosTokenType.SKULL)
        assert ctx.amount == -4

    def test_skull_hard(self):
        g, ctrl = _make_game("shattered_aeons")
        _set_hard(g)
        ctx = _token(g, ctrl, ChaosTokenType.SKULL)
        assert ctx.amount == -3
        inv = g.state.get_investigator("player")
        self._add_relic(g, inv)
        ctx = _token(g, ctrl, ChaosTokenType.SKULL)
        assert ctx.amount == -5

    def test_cultist_doom_nearest_unless_succeed_by_1(self):
        g, ctrl = _make_game("shattered_aeons")
        e1 = _add_enemy(g, "e1", "serpent_person", ["cultist"])
        ctx = _token(g, ctrl, ChaosTokenType.CULTIST)
        assert ctx.amount == -2
        _succeed(g, ctrl, difficulty=3, modified_skill=3)  # 优势0 → 放毁灭
        assert e1.doom == 1
        _token(g, ctrl, ChaosTokenType.CULTIST)
        _succeed(g, ctrl, difficulty=3, modified_skill=4)  # 优势1 → 无效果
        assert e1.doom == 1
        _token(g, ctrl, ChaosTokenType.CULTIST)
        _fail(g, ctrl)  # 失败 → 放毁灭
        assert e1.doom == 2

    def test_cultist_hard_each_cultist(self):
        g, ctrl = _make_game("shattered_aeons")
        _set_hard(g)
        e1 = _add_enemy(g, "e1", "serpent_person", ["cultist"])
        e2 = _add_enemy(g, "e2", "acolyte", ["cultist"], engaged=True)
        ctx = _token(g, ctrl, ChaosTokenType.CULTIST)
        assert ctx.amount == -3
        _fail(g, ctrl)
        assert e1.doom == 1
        assert e2.doom == 1

    def test_tablet_auto_fail_when_poisoned(self):
        g, ctrl = _make_game("shattered_aeons")
        _poison(g)
        ctx = _token(g, ctrl, ChaosTokenType.TABLET)
        assert ctx.amount == 0
        assert ctx.extra.get("force_auto_fail") is True

    def test_tablet_standard(self):
        g, ctrl = _make_game("shattered_aeons")
        ctx = _token(g, ctrl, ChaosTokenType.TABLET)
        assert ctx.amount == -2

    def test_tablet_hard_fail_marks_poisoned(self):
        g, ctrl = _make_game("shattered_aeons")
        _set_hard(g)
        ctx = _token(g, ctrl, ChaosTokenType.TABLET)
        assert ctx.amount == -3
        _fail(g, ctrl)
        assert "player" in g.state.scenario.vars["poisoned"]

    def test_elder_thing_hex_shuffle_on_fail(self):
        g, ctrl = _make_game("shattered_aeons")
        _make_treachery(g, "hex_old", ["hex"])
        _make_treachery(g, "not_hex", ["hazard"])
        _make_treachery(g, "hex_new", ["hex"])
        g.state.scenario.encounter_discard = ["hex_old", "not_hex", "hex_new"]
        ctx = _token(g, ctrl, ChaosTokenType.ELDER_THING)
        assert ctx.amount == -2
        _fail(g, ctrl)
        # 弃牌堆顶（最近的）Hex 诡计洗入探索牌堆
        assert g.state.scenario.vars["exploration_deck"] == ["hex_new"]
        assert g.state.scenario.encounter_discard == ["hex_old", "not_hex"]

    def test_elder_thing_hard_shuffles_immediately(self):
        g, ctrl = _make_game("shattered_aeons")
        _set_hard(g)
        _make_treachery(g, "hex1", ["hex"])
        g.state.scenario.encounter_discard = ["hex1"]
        ctx = _token(g, ctrl, ChaosTokenType.ELDER_THING)
        assert ctx.amount == -3
        assert g.state.scenario.vars["exploration_deck"] == ["hex1"]
        assert g.state.scenario.encounter_discard == []

    def test_elder_thing_no_hex_in_discard(self):
        g, ctrl = _make_game("shattered_aeons")
        ctx = _token(g, ctrl, ChaosTokenType.ELDER_THING)
        assert ctx.amount == -2
        _fail(g, ctrl)
        assert "exploration_deck" not in g.state.scenario.vars


class TestApplyTokenDispatch:
    def test_returns_false_for_non_tfa_scenario(self):
        g, ctrl = _make_game("the_gathering")
        inv = g.state.get_investigator("player")
        ctx = EventContext(
            game_state=g.state, event=GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="player", chaos_token=ChaosTokenType.SKULL, amount=0,
        )
        handled = tokens_tfa.apply_token(ctrl, ctx, inv, set(), set())
        assert handled is False

    def test_returns_false_for_numeric_token(self):
        g, ctrl = _make_game("wilds")
        inv = g.state.get_investigator("player")
        ctx = EventContext(
            game_state=g.state, event=GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="player", chaos_token=ChaosTokenType.MINUS_3, amount=0,
        )
        handled = tokens_tfa.apply_token(ctrl, ctx, inv, set(), set())
        assert handled is False

    def test_token_text_written(self):
        g, ctrl = _make_game("wilds")
        ctx = _token(g, ctrl, ChaosTokenType.SKULL)
        assert ctx.extra.get("token_text")
