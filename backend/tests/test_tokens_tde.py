"""Tests for The Dream-Eaters scenario chaos token effects.

直接驱动 backend.scenarios.tokens_tde 的 apply_token/on_fail/on_success
（该模块不挂事件总线，由调用方驱动；与 official_core / tokens_tic 同一约定）。
数值以 data/encounter_cards/the_dream_eaters.json 的 scenario 卡
text（Easy/Standard）/ back_text（Hard/Expert）为准。
"""

from backend.engine.event_bus import EventContext
from backend.models.enums import ChaosTokenType, GameEvent, Skill
from backend.scenarios.tokens_tde import apply_token, on_fail, on_success
from backend.tests.conftest import make_enemy_data, make_location_data
from backend.tests.test_scenario_tokens import _add_enemy, _make_game


def _mk(scenario_id, hard=False):
    g, ctrl = _make_game(scenario_id)
    g.state.scenario.vars["difficulty"] = "hard" if hard else "standard"
    return g, ctrl


def _add_location(game, loc_id, connections=(), traits=(), name=None):
    cd = make_location_data(id=loc_id, connections=list(connections))
    cd.traits = list(traits)
    if name is not None:
        cd.name = name
    game.register_card_data(cd)
    game.add_location(loc_id, cd, clues=0)
    return game.state.locations[loc_id]


class _Driver:
    """直接驱动 tokens_tde 三个入口的最小测试驱动器。"""

    def __init__(self, game, ctrl, inv_id="player"):
        self.g = game
        self.ctrl = ctrl
        self.inv_id = inv_id
        self.pending = set()
        self.success_pending = set()

    def token(self, token, skill_type=None, difficulty=3, source=None):
        ctx = EventContext(
            game_state=self.g.state,
            event=GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id=self.inv_id,
            chaos_token=token,
            amount=0,
            skill_type=skill_type,
            difficulty=difficulty,
            source=source,
        )
        inv = self.g.state.get_investigator(self.inv_id)
        handled = apply_token(self.ctrl, ctx, inv, self.pending, self.success_pending)
        assert handled
        return ctx

    def fail(self, difficulty=3, modified_skill=1, skill_type=None, source=None):
        ctx = EventContext(
            game_state=self.g.state,
            event=GameEvent.SKILL_TEST_FAILED,
            investigator_id=self.inv_id,
            success=False,
            difficulty=difficulty,
            modified_skill=modified_skill,
            skill_type=skill_type,
            source=source,
        )
        on_fail(self.ctrl, ctx, self.pending)
        return ctx

    def succeed(self, difficulty=3, modified_skill=5, skill_type=None, source=None):
        ctx = EventContext(
            game_state=self.g.state,
            event=GameEvent.SKILL_TEST_SUCCESSFUL,
            investigator_id=self.inv_id,
            success=True,
            difficulty=difficulty,
            modified_skill=modified_skill,
            skill_type=skill_type,
            source=source,
        )
        on_success(self.ctrl, ctx, self.success_pending)
        return ctx


class TestDispatch:
    def test_returns_false_for_non_tde_scenario(self):
        g, ctrl = _mk("the_gathering")
        ctx = EventContext(
            game_state=g.state, event=GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="player", chaos_token=ChaosTokenType.SKULL, amount=0,
        )
        inv = g.state.get_investigator("player")
        assert apply_token(ctrl, ctx, inv, set(), set()) is False

    def test_returns_false_for_numeric_token(self):
        g, ctrl = _mk("waking_nightmare")
        ctx = EventContext(
            game_state=g.state, event=GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="player", chaos_token=ChaosTokenType.MINUS_2, amount=-2,
        )
        inv = g.state.get_investigator("player")
        assert apply_token(ctrl, ctx, inv, set(), set()) is False


class TestBeyondTheGatesOfSleepTokens:
    def test_skull_standard_half_hand_rounded_up(self):
        g, ctrl = _mk("beyond_the_gates_of_sleep")
        inv = g.state.get_investigator("player")
        d = _Driver(g, ctrl)
        inv.hand = ["a", "b", "c", "d", "e"]
        assert d.token(ChaosTokenType.SKULL).amount == -3  # ceil(5/2)
        inv.hand = ["a", "b"]
        assert d.token(ChaosTokenType.SKULL).amount == -1

    def test_skull_hard_full_hand(self):
        g, ctrl = _mk("beyond_the_gates_of_sleep", hard=True)
        inv = g.state.get_investigator("player")
        d = _Driver(g, ctrl)
        inv.hand = ["a", "b", "c", "d", "e"]
        assert d.token(ChaosTokenType.SKULL).amount == -5

    def test_cultist_standard_counts_revealed_enchanted_woods(self):
        g, ctrl = _mk("beyond_the_gates_of_sleep")
        d = _Driver(g, ctrl)
        # 2 个已揭示的 Enchanted Woods（按 id/卡名匹配）
        _add_location(g, "enchanted_woods_a", traits=["woods"]).revealed = True
        _add_location(g, "enchanted_woods_b", traits=["woods"]).revealed = True
        # 未揭示的不计
        _add_location(g, "enchanted_woods_c", traits=["woods"])
        # 已揭示、有 woods 特质但非 Enchanted Woods（标准面不计）
        _add_location(g, "base_of_the_steps", traits=["steps", "woods"]).revealed = True
        assert d.token(ChaosTokenType.CULTIST).amount == -2

    def test_cultist_hard_counts_revealed_woods_trait(self):
        g, ctrl = _mk("beyond_the_gates_of_sleep", hard=True)
        d = _Driver(g, ctrl)
        _add_location(g, "enchanted_woods_a", traits=["woods"]).revealed = True
        _add_location(g, "enchanted_woods_b", traits=["woods"]).revealed = True
        _add_location(g, "enchanted_woods_c", traits=["woods"])
        _add_location(g, "base_of_the_steps", traits=["steps", "woods"]).revealed = True
        assert d.token(ChaosTokenType.CULTIST).amount == -3

    def test_tablet_standard_swarm_card_on_fail_vs_swarming(self):
        g, ctrl = _mk("beyond_the_gates_of_sleep")
        _add_enemy(g, "e1", "inconspicuous_zoog", ["swarming", "monster"], engaged=True)
        d = _Driver(g, ctrl)
        ctx = d.token(ChaosTokenType.TABLET, skill_type=Skill.COMBAT, source="e1")
        assert ctx.amount == -2
        d.fail(skill_type=Skill.COMBAT, source="e1")
        assert g.state.scenario.vars["swarm_cards"]["e1"] == 1

    def test_tablet_standard_no_effect_without_swarming_enemy(self):
        g, ctrl = _mk("beyond_the_gates_of_sleep")
        _add_enemy(g, "e1", "laboring_gug", ["monster"], engaged=True)
        d = _Driver(g, ctrl)
        ctx = d.token(ChaosTokenType.TABLET, skill_type=Skill.COMBAT, source="e1")
        assert ctx.amount == -2
        d.fail(skill_type=Skill.COMBAT, source="e1")
        assert "swarm_cards" not in g.state.scenario.vars

    def test_tablet_hard_swarm_card_immediately(self):
        g, ctrl = _mk("beyond_the_gates_of_sleep", hard=True)
        _add_enemy(g, "e1", "inconspicuous_zoog", ["swarming", "monster"], engaged=True)
        d = _Driver(g, ctrl)
        ctx = d.token(ChaosTokenType.TABLET, skill_type=Skill.AGILITY, source="e1")
        assert ctx.amount == -2
        assert g.state.scenario.vars["swarm_cards"]["e1"] == 1  # 无需失败


class TestWakingNightmareTokens:
    def test_skull_scales_with_engaged_staff_enemy(self):
        g, ctrl = _mk("waking_nightmare")
        d = _Driver(g, ctrl)
        assert d.token(ChaosTokenType.SKULL).amount == -1
        _add_enemy(g, "e1", "suspicious_orderly", ["humanoid", "staff"], engaged=True)
        assert d.token(ChaosTokenType.SKULL).amount == -3

    def test_skull_hard_scales_with_engaged_staff_enemy(self):
        g, ctrl = _mk("waking_nightmare", hard=True)
        d = _Driver(g, ctrl)
        assert d.token(ChaosTokenType.SKULL).amount == -2
        _add_enemy(g, "e1", "corrupted_orderly", ["humanoid", "staff", "spider"], engaged=True)
        assert d.token(ChaosTokenType.SKULL).amount == -4

    def test_cultist_reveals_another_and_infests_on_fail_agenda_2(self):
        g, ctrl = _mk("waking_nightmare")
        g.chaos_bag.tokens = [ChaosTokenType.MINUS_3]
        g.state.scenario.current_agenda_index = 1  # 密谋2
        d = _Driver(g, ctrl)
        assert d.token(ChaosTokenType.CULTIST).amount == -3  # 0 + 再揭示(-3)
        assert "infestation_tests_made" not in g.state.scenario.vars
        d.fail()
        assert g.state.scenario.vars["infestation_tests_made"] == 1

    def test_cultist_no_infestation_on_agenda_1(self):
        g, ctrl = _mk("waking_nightmare")
        g.chaos_bag.tokens = [ChaosTokenType.MINUS_1]
        g.state.scenario.current_agenda_index = 0  # 密谋1
        d = _Driver(g, ctrl)
        assert d.token(ChaosTokenType.CULTIST).amount == -1
        d.fail()
        assert "infestation_tests_made" not in g.state.scenario.vars

    def test_cultist_hard_infests_immediately_on_agenda_3(self):
        g, ctrl = _mk("waking_nightmare", hard=True)
        g.chaos_bag.tokens = [ChaosTokenType.MINUS_2]
        g.state.scenario.current_agenda_index = 2  # 密谋3
        d = _Driver(g, ctrl)
        assert d.token(ChaosTokenType.CULTIST).amount == -2
        assert g.state.scenario.vars["infestation_tests_made"] == 1  # 无需失败

    def test_elder_thing_minus_infested_locations(self):
        g, ctrl = _mk("waking_nightmare")
        d = _Driver(g, ctrl)
        g.state.scenario.vars["infested_locations"] = ["morgue", "stairwell"]
        assert d.token(ChaosTokenType.ELDER_THING).amount == -2

    def test_elder_thing_hard_one_higher(self):
        g, ctrl = _mk("waking_nightmare", hard=True)
        d = _Driver(g, ctrl)
        g.state.scenario.vars["infested_locations"] = ["morgue", "stairwell"]
        assert d.token(ChaosTokenType.ELDER_THING).amount == -3


class TestSearchForKadathTokens:
    def test_skull_minus_signs_of_gods(self):
        g, ctrl = _mk("the_search_for_kadath")
        d = _Driver(g, ctrl)
        g.state.scenario.vars["signs_of_gods"] = 2
        assert d.token(ChaosTokenType.SKULL).amount == -2

    def test_skull_hard_one_more(self):
        g, ctrl = _mk("the_search_for_kadath", hard=True)
        d = _Driver(g, ctrl)
        g.state.scenario.vars["signs_of_gods"] = 2
        assert d.token(ChaosTokenType.SKULL).amount == -3

    def test_cultist_shroud_bonus_on_failed_investigation(self):
        g, ctrl = _mk("the_search_for_kadath")
        g.chaos_bag.tokens = [ChaosTokenType.ZERO]
        d = _Driver(g, ctrl)
        ctx = d.token(ChaosTokenType.CULTIST, skill_type=Skill.INTELLECT)
        assert ctx.amount == 0
        d.fail(skill_type=Skill.INTELLECT)
        assert g.state.scenario.vars["shroud_bonus_round"]["test_location"] == 1

    def test_cultist_hard_shroud_bonus_2(self):
        g, ctrl = _mk("the_search_for_kadath", hard=True)
        g.chaos_bag.tokens = [ChaosTokenType.ZERO]
        d = _Driver(g, ctrl)
        d.token(ChaosTokenType.CULTIST, skill_type=Skill.INTELLECT)
        d.fail(skill_type=Skill.INTELLECT)
        assert g.state.scenario.vars["shroud_bonus_round"]["test_location"] == 2

    def test_cultist_no_shroud_bonus_outside_investigation(self):
        g, ctrl = _mk("the_search_for_kadath")
        g.chaos_bag.tokens = [ChaosTokenType.ZERO]
        d = _Driver(g, ctrl)
        d.token(ChaosTokenType.CULTIST, skill_type=Skill.COMBAT)
        d.fail(skill_type=Skill.COMBAT)
        assert "shroud_bonus_round" not in g.state.scenario.vars

    def test_tablet_fail_takes_damage_and_horror(self):
        g, ctrl = _mk("the_search_for_kadath")
        inv = g.state.get_investigator("player")
        d = _Driver(g, ctrl)
        assert d.token(ChaosTokenType.TABLET).amount == -2
        d.fail()
        assert inv.damage == 1
        assert inv.horror == 1
        assert g.state.scenario.doom_on_agenda == 0

    def test_tablet_fail_places_doom_when_damage_would_defeat(self):
        g, ctrl = _mk("the_search_for_kadath", hard=True)
        inv = g.state.get_investigator("player")
        inv.damage = 6  # health 7，再受1伤害即致败
        d = _Driver(g, ctrl)
        assert d.token(ChaosTokenType.TABLET).amount == -3
        d.fail()
        assert inv.damage == 6
        assert g.state.scenario.doom_on_agenda == 1

    def test_elder_thing_extra_clue_on_successful_investigation(self):
        g, ctrl = _mk("the_search_for_kadath")
        inv = g.state.get_investigator("player")
        loc = g.state.get_location("test_location")
        loc.clues = 2
        d = _Driver(g, ctrl)
        assert d.token(ChaosTokenType.ELDER_THING, skill_type=Skill.INTELLECT).amount == 2
        d.succeed(skill_type=Skill.INTELLECT)
        assert inv.clues == 1
        assert loc.clues == 1

    def test_elder_thing_hard_plus_one(self):
        g, ctrl = _mk("the_search_for_kadath", hard=True)
        d = _Driver(g, ctrl)
        assert d.token(ChaosTokenType.ELDER_THING, skill_type=Skill.INTELLECT).amount == 1


class TestThousandShapesOfHorrorTokens:
    def test_skull_scales_with_graveyard_location(self):
        g, ctrl = _mk("a_thousand_shapes_of_horror")
        d = _Driver(g, ctrl)
        assert d.token(ChaosTokenType.SKULL).amount == -1
        g.state.get_location("test_location").card_data.traits = ["graveyard"]
        assert d.token(ChaosTokenType.SKULL).amount == -3

    def test_skull_hard_scales_with_graveyard_location(self):
        g, ctrl = _mk("a_thousand_shapes_of_horror", hard=True)
        d = _Driver(g, ctrl)
        assert d.token(ChaosTokenType.SKULL).amount == -2
        g.state.get_location("test_location").card_data.traits = ["graveyard"]
        assert d.token(ChaosTokenType.SKULL).amount == -4

    def test_cultist_unnamable_attacks_on_fail(self):
        g, ctrl = _mk("a_thousand_shapes_of_horror")
        g.chaos_bag.tokens = [ChaosTokenType.MINUS_1]
        inv = g.state.get_investigator("player")
        _add_location(g, "far_place")
        _add_enemy(g, "e1", "the_unnamable", ["monster", "elite"], location="far_place")
        d = _Driver(g, ctrl)
        assert d.token(ChaosTokenType.CULTIST).amount == -1
        d.fail()
        assert inv.damage == 1  # 无视距离立刻攻击（默认敌卡 1伤害1恐惧）
        assert inv.horror == 1

    def test_cultist_no_attack_without_unnamable(self):
        g, ctrl = _mk("a_thousand_shapes_of_horror")
        g.chaos_bag.tokens = [ChaosTokenType.MINUS_1]
        inv = g.state.get_investigator("player")
        d = _Driver(g, ctrl)
        d.token(ChaosTokenType.CULTIST)
        d.fail()
        assert inv.damage == 0
        assert inv.horror == 0

    def test_tablet_evades_highest_fight_enemy_within_margin(self):
        g, ctrl = _mk("a_thousand_shapes_of_horror")
        weak = _add_enemy(g, "e1", "weak_foe", ["monster"], engaged=True)
        g.state.get_card_data("weak_foe").enemy_fight = 2
        strong = _add_enemy(g, "e2", "strong_foe", ["monster"])
        g.state.get_card_data("strong_foe").enemy_fight = 4
        d = _Driver(g, ctrl)
        assert d.token(ChaosTokenType.TABLET).amount == 2
        # 成功超出值 3：仅 weak(fight 2) 可被躲避
        d.succeed(difficulty=3, modified_skill=6)
        assert weak.exhausted is True
        assert "e1" not in g.state.get_investigator("player").threat_area
        assert strong.exhausted is False

    def test_tablet_hard_plus_one(self):
        g, ctrl = _mk("a_thousand_shapes_of_horror", hard=True)
        d = _Driver(g, ctrl)
        assert d.token(ChaosTokenType.TABLET).amount == 1

    def test_elder_thing_fail_takes_damage(self):
        g, ctrl = _mk("a_thousand_shapes_of_horror")
        inv = g.state.get_investigator("player")
        d = _Driver(g, ctrl)
        assert d.token(ChaosTokenType.ELDER_THING).amount == -2
        d.fail()
        assert inv.damage == 1

    def test_elder_thing_fail_places_clue_when_damage_would_defeat(self):
        g, ctrl = _mk("a_thousand_shapes_of_horror", hard=True)
        inv = g.state.get_investigator("player")
        loc = g.state.get_location("test_location")
        inv.damage = 6  # 再受1伤害即致败
        inv.clues = 2
        loc.clues = 1
        d = _Driver(g, ctrl)
        assert d.token(ChaosTokenType.ELDER_THING).amount == -3
        d.fail()
        assert inv.damage == 6
        assert inv.clues == 1
        assert loc.clues == 2


class TestDarkSideOfTheMoonTokens:
    def test_skull_standard_half_alarm_rounded_up(self):
        g, ctrl = _mk("dark_side_of_the_moon")
        d = _Driver(g, ctrl)
        g.state.scenario.vars["alarm_levels"] = {"player": 3}
        assert d.token(ChaosTokenType.SKULL).amount == -2  # ceil(3/2)
        g.state.scenario.vars["alarm_levels"] = {"player": 0}
        assert d.token(ChaosTokenType.SKULL).amount == 0

    def test_skull_hard_full_alarm(self):
        g, ctrl = _mk("dark_side_of_the_moon", hard=True)
        d = _Driver(g, ctrl)
        g.state.scenario.vars["alarm_levels"] = {"player": 3}
        assert d.token(ChaosTokenType.SKULL).amount == -3

    def test_cultist_draws_encounter_when_alarm_exceeds_skill(self):
        g, ctrl = _mk("dark_side_of_the_moon")
        g.chaos_bag.tokens = [ChaosTokenType.MINUS_2]
        g.state.scenario.vars["alarm_levels"] = {"player": 2}
        g.state.scenario.encounter_deck = ["enc_a", "enc_b"]
        d = _Driver(g, ctrl)
        assert d.token(ChaosTokenType.CULTIST).amount == -2
        d.fail(modified_skill=1)  # 警报2 > 修正值1
        assert g.state.scenario.encounter_deck == ["enc_b"]
        assert g.state.scenario.vars["token_drawn_encounters"] == ["enc_a"]

    def test_cultist_no_draw_when_alarm_not_higher(self):
        g, ctrl = _mk("dark_side_of_the_moon")
        g.chaos_bag.tokens = [ChaosTokenType.MINUS_2]
        g.state.scenario.vars["alarm_levels"] = {"player": 1}
        g.state.scenario.encounter_deck = ["enc_a"]
        d = _Driver(g, ctrl)
        d.token(ChaosTokenType.CULTIST)
        d.fail(modified_skill=1)  # 警报1 不高于 修正值1
        assert g.state.scenario.encounter_deck == ["enc_a"]

    def test_tablet_raises_alarm_on_fail(self):
        g, ctrl = _mk("dark_side_of_the_moon")
        d = _Driver(g, ctrl)
        assert d.token(ChaosTokenType.TABLET).amount == -1
        d.fail()
        assert g.state.scenario.vars["alarm_levels"]["player"] == 1

    def test_tablet_hard_minus_two(self):
        g, ctrl = _mk("dark_side_of_the_moon", hard=True)
        d = _Driver(g, ctrl)
        assert d.token(ChaosTokenType.TABLET).amount == -2

    def test_elder_thing_evasion_success_deals_2_damage(self):
        g, ctrl = _mk("dark_side_of_the_moon")
        enemy = _add_enemy(g, "e1", "nightriders", ["creature", "monster"], engaged=True)
        d = _Driver(g, ctrl)
        assert d.token(ChaosTokenType.ELDER_THING, skill_type=Skill.AGILITY).amount == 1
        d.succeed(skill_type=Skill.AGILITY, source="e1")
        assert enemy.damage == 2

    def test_elder_thing_hard_zero(self):
        g, ctrl = _mk("dark_side_of_the_moon", hard=True)
        d = _Driver(g, ctrl)
        assert d.token(ChaosTokenType.ELDER_THING, skill_type=Skill.AGILITY).amount == 0


class TestPointOfNoReturnTokens:
    def test_skull_minus_scenario_card_damage(self):
        g, ctrl = _mk("point_of_no_return")
        d = _Driver(g, ctrl)
        g.state.scenario.vars["scenario_card_damage"] = 2
        assert d.token(ChaosTokenType.SKULL).amount == -2

    def test_skull_hard_one_more(self):
        g, ctrl = _mk("point_of_no_return", hard=True)
        d = _Driver(g, ctrl)
        g.state.scenario.vars["scenario_card_damage"] = 2
        assert d.token(ChaosTokenType.SKULL).amount == -3

    def test_cultist_draws_encounter_on_fail(self):
        g, ctrl = _mk("point_of_no_return")
        g.chaos_bag.tokens = [ChaosTokenType.ZERO]
        g.state.scenario.encounter_deck = ["enc_a", "enc_b"]
        d = _Driver(g, ctrl)
        assert d.token(ChaosTokenType.CULTIST).amount == 0
        d.fail()
        assert g.state.scenario.encounter_deck == ["enc_b"]
        assert g.state.scenario.vars["token_drawn_encounters"] == ["enc_a"]

    def test_tablet_draws_card_on_successful_investigation(self):
        g, ctrl = _mk("point_of_no_return")
        inv = g.state.get_investigator("player")
        inv.deck = ["card_a", "card_b"]
        d = _Driver(g, ctrl)
        assert d.token(ChaosTokenType.TABLET, skill_type=Skill.INTELLECT).amount == 1
        d.succeed(skill_type=Skill.INTELLECT)
        assert inv.hand == ["card_a"]
        assert inv.deck == ["card_b"]

    def test_tablet_hard_zero(self):
        g, ctrl = _mk("point_of_no_return", hard=True)
        d = _Driver(g, ctrl)
        assert d.token(ChaosTokenType.TABLET, skill_type=Skill.INTELLECT).amount == 0

    def test_elder_thing_fail_by_2_pulls_weakest_ready_enemy(self):
        g, ctrl = _mk("point_of_no_return")
        inv = g.state.get_investigator("player")
        g.state.get_location("test_location").card_data.connections = ["loc2"]
        _add_location(g, "loc2", connections=["test_location"])
        # 连接地点的弱敌人（1伤害1恐惧）与本地点的强敌人（2伤害2恐惧）
        _add_enemy(g, "e1", "weak_foe", ["monster"], location="loc2")
        cd_weak = g.state.get_card_data("weak_foe")
        cd_weak.enemy_damage, cd_weak.enemy_horror = 1, 1
        _add_enemy(g, "e2", "strong_foe", ["monster"], location="test_location")
        cd_strong = g.state.get_card_data("strong_foe")
        cd_strong.enemy_damage, cd_strong.enemy_horror = 2, 2
        d = _Driver(g, ctrl)
        assert d.token(ChaosTokenType.ELDER_THING).amount == -3
        d.fail(difficulty=3, modified_skill=1)  # 失败2点
        assert "e1" in inv.threat_area  # 自动选最弱：移至你处并交战
        assert "e1" not in g.state.get_location("loc2").enemies
        assert inv.damage == 1
        assert inv.horror == 1
        assert "e2" in g.state.get_location("test_location").enemies  # 强敌人不动

    def test_elder_thing_fail_by_1_no_effect(self):
        g, ctrl = _mk("point_of_no_return", hard=True)
        inv = g.state.get_investigator("player")
        _add_enemy(g, "e1", "weak_foe", ["monster"])
        d = _Driver(g, ctrl)
        assert d.token(ChaosTokenType.ELDER_THING).amount == -4
        d.fail(difficulty=3, modified_skill=2)  # 失败1点
        assert "e1" not in inv.threat_area
        assert inv.damage == 0


class TestWhereGodsDwellTokens:
    def test_skull_standard_is_current_act_number(self):
        g, ctrl = _mk("where_gods_dwell")
        d = _Driver(g, ctrl)
        g.state.scenario.current_act_index = 0
        assert d.token(ChaosTokenType.SKULL).amount == -1
        g.state.scenario.current_act_index = 2
        assert d.token(ChaosTokenType.SKULL).amount == -3

    def test_skull_hard_act_plus_agenda(self):
        g, ctrl = _mk("where_gods_dwell", hard=True)
        d = _Driver(g, ctrl)
        g.state.scenario.current_act_index = 1   # 剧情2
        g.state.scenario.current_agenda_index = 2  # 密谋3
        assert d.token(ChaosTokenType.SKULL).amount == -5

    def test_cultist_places_doom_on_fail(self):
        g, ctrl = _mk("where_gods_dwell")
        g.chaos_bag.tokens = [ChaosTokenType.MINUS_1]
        d = _Driver(g, ctrl)
        assert d.token(ChaosTokenType.CULTIST).amount == -1
        d.fail()
        assert g.state.scenario.doom_on_agenda == 1

    def test_tablet_reveals_nyarlathotep_from_hand_on_fail(self):
        g, ctrl = _mk("where_gods_dwell")
        inv = g.state.get_investigator("player")
        g.register_card_data(make_enemy_data(id="nyarlathotep_a", name="Nyarlathotep"))
        g.state.get_card_data("nyarlathotep_a").enemy_damage = 2
        g.state.get_card_data("nyarlathotep_a").enemy_horror = 1
        inv.hand = ["nyarlathotep_a", "other_card"]
        g.state.scenario.encounter_deck = ["enc_a"]
        d = _Driver(g, ctrl)
        assert d.token(ChaosTokenType.TABLET).amount == -4
        d.fail()
        assert inv.hand == ["other_card"]
        assert inv.damage == 2
        assert inv.horror == 1
        assert sorted(g.state.scenario.encounter_deck) == ["enc_a", "nyarlathotep_a"]

    def test_tablet_no_nyarlathotep_in_hand(self):
        g, ctrl = _mk("where_gods_dwell", hard=True)
        inv = g.state.get_investigator("player")
        inv.hand = ["other_card"]
        d = _Driver(g, ctrl)
        assert d.token(ChaosTokenType.TABLET).amount == -6
        d.fail()
        assert inv.hand == ["other_card"]
        assert inv.damage == 0

    def test_elder_thing_values(self):
        g, ctrl = _mk("where_gods_dwell")
        d = _Driver(g, ctrl)
        assert d.token(ChaosTokenType.ELDER_THING).amount == 0
        g2, ctrl2 = _mk("where_gods_dwell", hard=True)
        d2 = _Driver(g2, ctrl2)
        assert d2.token(ChaosTokenType.ELDER_THING).amount == -1


class TestWeaverOfTheCosmosTokens:
    def test_skull_standard_highest_location_doom(self):
        g, ctrl = _mk("weaver_of_the_cosmos")
        _add_location(g, "loc2")
        g.state.get_location("test_location").doom = 2
        g.state.get_location("loc2").doom = 3
        d = _Driver(g, ctrl)
        assert d.token(ChaosTokenType.SKULL).amount == -3

    def test_skull_hard_total_location_doom(self):
        g, ctrl = _mk("weaver_of_the_cosmos", hard=True)
        _add_location(g, "loc2")
        g.state.get_location("test_location").doom = 2
        g.state.get_location("loc2").doom = 3
        d = _Driver(g, ctrl)
        assert d.token(ChaosTokenType.SKULL).amount == -5

    def test_cultist_ancient_one_at_location_attacks_on_fail(self):
        g, ctrl = _mk("weaver_of_the_cosmos")
        g.chaos_bag.tokens = [ChaosTokenType.ZERO]
        inv = g.state.get_investigator("player")
        _add_enemy(g, "e1", "atlatl_nacha", ["ancient_one", "spider"], engaged=True)
        d = _Driver(g, ctrl)
        assert d.token(ChaosTokenType.CULTIST).amount == 0
        d.fail()
        assert inv.damage == 1
        assert inv.horror == 1

    def test_cultist_no_ancient_one_no_attack(self):
        g, ctrl = _mk("weaver_of_the_cosmos")
        g.chaos_bag.tokens = [ChaosTokenType.ZERO]
        inv = g.state.get_investigator("player")
        _add_enemy(g, "e1", "swarm_of_spiders", ["creature", "spider"])
        d = _Driver(g, ctrl)
        d.token(ChaosTokenType.CULTIST)
        d.fail()
        assert inv.damage == 0

    def test_tablet_removes_doom_on_succeed_by_2(self):
        g, ctrl = _mk("weaver_of_the_cosmos")
        loc = g.state.get_location("test_location")
        loc.doom = 1
        d = _Driver(g, ctrl)
        assert d.token(ChaosTokenType.TABLET).amount == 0
        d.succeed(difficulty=3, modified_skill=5)  # 成功2点
        assert loc.doom == 0

    def test_tablet_no_remove_when_succeed_by_1(self):
        g, ctrl = _mk("weaver_of_the_cosmos", hard=True)
        loc = g.state.get_location("test_location")
        loc.doom = 1
        d = _Driver(g, ctrl)
        assert d.token(ChaosTokenType.TABLET).amount == -1
        d.succeed(difficulty=3, modified_skill=4)  # 成功1点
        assert loc.doom == 1

    def test_elder_thing_spider_attack_fail_places_doom(self):
        g, ctrl = _mk("weaver_of_the_cosmos")
        _add_location(g, "web")
        _add_enemy(g, "e1", "spider_of_leng", ["monster", "spider"], location="web")
        d = _Driver(g, ctrl)
        assert d.token(ChaosTokenType.ELDER_THING, skill_type=Skill.COMBAT, source="e1").amount == -3
        d.fail(skill_type=Skill.COMBAT, source="e1")
        assert g.state.get_location("web").doom == 1

    def test_elder_thing_no_doom_for_non_spider(self):
        g, ctrl = _mk("weaver_of_the_cosmos", hard=True)
        _add_enemy(g, "e1", "laboring_gug", ["monster"])
        d = _Driver(g, ctrl)
        assert d.token(ChaosTokenType.ELDER_THING, skill_type=Skill.COMBAT, source="e1").amount == -4
        d.fail(skill_type=Skill.COMBAT, source="e1")
        assert g.state.get_location("test_location").doom == 0
