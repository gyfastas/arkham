"""Tests for Edge of the Earth scenario chaos token effects (tokens_eoe)."""

from backend.engine.event_bus import EventContext
from backend.models.enums import ChaosTokenType, GameEvent
from backend.models.state import CardInstance
from backend.scenarios.tokens_eoe import apply_token, on_fail, on_success
from backend.tests.conftest import make_asset_data, make_location_data
from backend.tests.test_scenario_tokens import _add_enemy, _make_game


def _apply(game, ctrl, token, inv_id="player", extra=None):
    """直接驱动 apply_token，返回 (ctx, pending, success_pending, handled)。"""
    inv = game.state.get_investigator(inv_id)
    ctx = EventContext(
        game_state=game.state, event=GameEvent.CHAOS_TOKEN_RESOLVED,
        investigator_id=inv_id, chaos_token=token, amount=0,
        extra=dict(extra or {}),
    )
    pending: set[str] = set()
    success_pending: set[str] = set()
    handled = apply_token(ctrl, ctx, inv, pending, success_pending)
    return ctx, pending, success_pending, handled


def _fail(game, ctrl, pending, difficulty=3, modified_skill=1, inv_id="player"):
    ctx = EventContext(
        game_state=game.state, event=GameEvent.SKILL_TEST_FAILED,
        investigator_id=inv_id, success=False,
        difficulty=difficulty, modified_skill=modified_skill,
    )
    on_fail(ctrl, ctx, pending)
    return ctx


def _succeed(game, ctrl, success_pending, difficulty=3, modified_skill=5, inv_id="player"):
    ctx = EventContext(
        game_state=game.state, event=GameEvent.SKILL_TEST_SUCCESSFUL,
        investigator_id=inv_id, success=True,
        difficulty=difficulty, modified_skill=modified_skill,
    )
    on_success(ctrl, ctx, success_pending)
    return ctx


def _hard(game):
    game.state.scenario.vars["difficulty"] = "hard"


def _set_tekeli_li(game, cards):
    game.state.scenario.vars["tekeli_li_deck"] = list(cards)


def _add_location(game, location_id, *, level=None, connections=None):
    data = make_location_data(id=location_id, connections=list(connections or []))
    if level is not None:
        data.level = level
    game.register_card_data(data)
    game.add_location(location_id, data)
    return game.state.locations[location_id]


def _set_location_level(game, location_id, level):
    game.state.locations[location_id].card_data.level = level


def _add_asset_to_play(game, instance_id, card_id, *, cost=1, traits=None, inv_id="player"):
    cd = make_asset_data(id=card_id, cost=cost, traits=traits or [])
    game.register_card_data(cd)
    inst = CardInstance(
        instance_id=instance_id, card_id=card_id,
        owner_id=inv_id, controller_id=inv_id,
    )
    game.state.cards_in_play[instance_id] = inst
    game.state.get_investigator(inv_id).play_area.append(instance_id)
    return inst


class TestIceAndDeathTokens:
    def test_skull_half_shelter_rounded_up_standard(self):
        g, ctrl = _make_game("ice_and_death_part_1")
        g.state.locations["test_location"].card_data.text = "...\n<b>Shelter 3.</b>"
        ctx, *_ , handled = _apply(g, ctrl, ChaosTokenType.SKULL)
        assert handled is True
        assert ctx.amount == -2  # ceil(3/2)

    def test_skull_full_shelter_hard(self):
        g, ctrl = _make_game("ice_and_death_part_3")
        _hard(g)
        g.state.locations["test_location"].card_data.text = "<b>Shelter 3.</b>"
        ctx, *_ , handled = _apply(g, ctrl, ChaosTokenType.SKULL)
        assert handled is True
        assert ctx.amount == -3

    def test_skull_shelter_from_chinese_text(self):
        g, ctrl = _make_game("ice_and_death_part_2")
        g.state.locations["test_location"].card_data.text = ""
        g.state.locations["test_location"].card_data.text_cn = "<b>庇護2</b>。"
        ctx, *_ = _apply(g, ctrl, ChaosTokenType.SKULL)
        assert ctx.amount == -1  # ceil(2/2)

    def test_cultist_fail_shuffles_tekeli_li_into_deck(self):
        g, ctrl = _make_game("ice_and_death_part_1")
        _set_tekeli_li(g, ["tekeli_li_a"])
        inv = g.state.get_investigator("player")
        inv.deck = ["c1"]
        ctx, pending, _, _ = _apply(g, ctrl, ChaosTokenType.CULTIST)
        assert ctx.amount == -2
        _fail(g, ctrl, pending)
        assert g.state.scenario.vars["tekeli_li_deck"] == []
        assert sorted(inv.deck) == ["c1", "tekeli_li_a"]
        assert inv.horror == 0

    def test_cultist_fail_empty_tekeli_li_takes_horror(self):
        g, ctrl = _make_game("ice_and_death_part_1")
        inv = g.state.get_investigator("player")
        inv.horror = 0
        _, pending, _, _ = _apply(g, ctrl, ChaosTokenType.CULTIST)
        _fail(g, ctrl, pending)
        assert inv.horror == 1

    def test_cultist_hard_fail_per_point(self):
        g, ctrl = _make_game("ice_and_death_part_1")
        _hard(g)
        _set_tekeli_li(g, ["tekeli_li_a"])  # 只有1张可洗
        inv = g.state.get_investigator("player")
        inv.deck = []
        inv.horror = 0
        _, pending, _, _ = _apply(g, ctrl, ChaosTokenType.CULTIST)
        _fail(g, ctrl, pending, difficulty=3, modified_skill=1)  # 失败2点
        assert inv.deck == ["tekeli_li_a"]  # 洗入1张
        assert inv.horror == 1  # 另1张不能洗 → 1恐惧

    def test_tablet_fail_discards_per_point_and_draws_weakness(self):
        g, ctrl = _make_game("ice_and_death_part_1")
        w = make_asset_data(id="w1")
        w.subtype = "weakness"
        g.register_card_data(w)
        inv = g.state.get_investigator("player")
        inv.deck = ["c1", "w1", "c2"]
        ctx, pending, _, _ = _apply(g, ctrl, ChaosTokenType.TABLET)
        assert ctx.amount == -3
        _fail(g, ctrl, pending, difficulty=3, modified_skill=1)  # 失败2点
        assert inv.deck == ["c2"]
        assert inv.discard == ["c1"]
        assert inv.hand == ["w1"]  # 弃掉的弱点入手

    def test_tablet_hard_is_minus4(self):
        g, ctrl = _make_game("ice_and_death_part_1")
        _hard(g)
        ctx, pending, _, _ = _apply(g, ctrl, ChaosTokenType.TABLET)
        assert ctx.amount == -4
        assert "iad_tablet_discard_margin" in pending


class TestFatalMirageTokens:
    def test_skull_story_cards_in_victory_standard(self):
        g, ctrl = _make_game("fatal_mirage")
        g.register_card_data(make_asset_data(id="story1"))
        g.register_card_data(make_asset_data(id="story2"))
        g.state.scenario.victory_display = ["story1", "story2", "unknown_enemy"]
        ctx, *_ = _apply(g, ctrl, ChaosTokenType.SKULL)
        assert ctx.amount == -2  # 敌人不计入

    def test_skull_hard_adds_agenda_number(self):
        g, ctrl = _make_game("fatal_mirage")
        _hard(g)
        g.register_card_data(make_asset_data(id="story1"))
        g.state.scenario.victory_display = ["story1"]
        g.state.scenario.current_agenda_index = 1  # 密谋2
        ctx, *_ = _apply(g, ctrl, ChaosTokenType.SKULL)
        assert ctx.amount == -3  # 1 + 2

    def test_cultist_fail_places_clue(self):
        g, ctrl = _make_game("fatal_mirage")
        inv = g.state.get_investigator("player")
        inv.clues = 2
        loc = g.state.locations["test_location"]
        loc.clues = 3
        ctx, pending, _, _ = _apply(g, ctrl, ChaosTokenType.CULTIST)
        assert ctx.amount == -2
        _fail(g, ctrl, pending)
        assert inv.clues == 1
        assert loc.clues == 4

    def test_cultist_hard_triggers_on_success_by_less_than_2(self):
        g, ctrl = _make_game("fatal_mirage")
        _hard(g)
        inv = g.state.get_investigator("player")
        inv.clues = 1
        loc = g.state.locations["test_location"]
        loc.clues = 0
        _, pending, success_pending, _ = _apply(g, ctrl, ChaosTokenType.CULTIST)
        # 成功但只超出1点 → 仍触发
        _succeed(g, ctrl, success_pending, difficulty=3, modified_skill=4)
        assert inv.clues == 0
        assert loc.clues == 1

    def test_cultist_hard_no_trigger_on_success_by_2(self):
        g, ctrl = _make_game("fatal_mirage")
        _hard(g)
        inv = g.state.get_investigator("player")
        inv.clues = 1
        _, pending, success_pending, _ = _apply(g, ctrl, ChaosTokenType.CULTIST)
        _succeed(g, ctrl, success_pending, difficulty=3, modified_skill=5)
        assert inv.clues == 1
        # 失败路径无条件触发
        _fail(g, ctrl, pending)
        assert inv.clues == 0

    def test_tablet_fail_prefers_tekeli_li_shuffle(self):
        g, ctrl = _make_game("fatal_mirage")
        _set_tekeli_li(g, ["tekeli_li_a"])
        _add_location(g, "prison_of_memories")
        inv = g.state.get_investigator("player")
        inv.deck = []
        ctx, pending, _, _ = _apply(g, ctrl, ChaosTokenType.TABLET)
        assert ctx.amount == -3
        _fail(g, ctrl, pending)
        assert inv.deck == ["tekeli_li_a"]  # 二选一自动取洗牌
        assert inv.location_id == "test_location"  # 未移动

    def test_tablet_fail_moves_to_prison_when_tekeli_li_empty(self):
        g, ctrl = _make_game("fatal_mirage")
        _add_location(g, "prison_of_memories")
        inv = g.state.get_investigator("player")
        _, pending, _, _ = _apply(g, ctrl, ChaosTokenType.TABLET)
        _fail(g, ctrl, pending)
        assert inv.location_id == "prison_of_memories"

    def test_tablet_hard_fail_by_2_does_both(self):
        g, ctrl = _make_game("fatal_mirage")
        _hard(g)
        _set_tekeli_li(g, ["tekeli_li_a"])
        _add_location(g, "prison_of_memories")
        inv = g.state.get_investigator("player")
        inv.deck = []
        ctx, pending, _, _ = _apply(g, ctrl, ChaosTokenType.TABLET)
        assert ctx.amount == -4
        _fail(g, ctrl, pending, difficulty=3, modified_skill=1)  # 失败2点
        assert inv.deck == ["tekeli_li_a"]
        assert inv.location_id == "prison_of_memories"

    def test_elder_thing_fail_dooms_eidolon(self):
        g, ctrl = _make_game("fatal_mirage")
        e = _add_enemy(g, "e1", "horrifying_shade", ["eidolon"])
        _add_enemy(g, "e2", "some_monster", ["monster"])
        ctx, pending, _, _ = _apply(g, ctrl, ChaosTokenType.ELDER_THING)
        assert ctx.amount == -4
        _fail(g, ctrl, pending)
        assert e.doom == 1

    def test_elder_thing_hard_is_minus5(self):
        g, ctrl = _make_game("fatal_mirage")
        _hard(g)
        ctx, *_ = _apply(g, ctrl, ChaosTokenType.ELDER_THING)
        assert ctx.amount == -5


class TestForbiddenPeaksTokens:
    def test_skull_is_location_level(self):
        g, ctrl = _make_game("to_the_forbidden_peaks")
        _set_location_level(g, "test_location", 3)
        ctx, *_ = _apply(g, ctrl, ChaosTokenType.SKULL)
        assert ctx.amount == -3

    def test_skull_hard_adds_2(self):
        g, ctrl = _make_game("to_the_forbidden_peaks")
        _hard(g)
        _set_location_level(g, "test_location", 3)
        ctx, *_ = _apply(g, ctrl, ChaosTokenType.SKULL)
        assert ctx.amount == -5

    def test_cultist_fail_moves_down(self):
        g, ctrl = _make_game("to_the_forbidden_peaks")
        _set_location_level(g, "test_location", 2)
        g.state.locations["test_location"].card_data.connections = ["below_loc"]
        _add_location(g, "below_loc", level=1, connections=["test_location"])
        inv = g.state.get_investigator("player")
        ctx, pending, _, _ = _apply(g, ctrl, ChaosTokenType.CULTIST)
        assert ctx.amount == -1
        _fail(g, ctrl, pending)
        assert inv.location_id == "below_loc"

    def test_cultist_standard_success_does_not_move(self):
        g, ctrl = _make_game("to_the_forbidden_peaks")
        _set_location_level(g, "test_location", 2)
        g.state.locations["test_location"].card_data.connections = ["below_loc"]
        _add_location(g, "below_loc", level=1, connections=["test_location"])
        inv = g.state.get_investigator("player")
        _, pending, success_pending, _ = _apply(g, ctrl, ChaosTokenType.CULTIST)
        _succeed(g, ctrl, success_pending)
        assert inv.location_id == "test_location"

    def test_cultist_hard_moves_even_on_success(self):
        g, ctrl = _make_game("to_the_forbidden_peaks")
        _hard(g)
        _set_location_level(g, "test_location", 2)
        g.state.locations["test_location"].card_data.connections = ["below_loc"]
        _add_location(g, "below_loc", level=1, connections=["test_location"])
        inv = g.state.get_investigator("player")
        _, pending, success_pending, _ = _apply(g, ctrl, ChaosTokenType.CULTIST)
        _succeed(g, ctrl, success_pending)
        assert inv.location_id == "below_loc"

    def test_tablet_fail_loses_expedition_asset_to_location(self):
        g, ctrl = _make_game("to_the_forbidden_peaks")
        inv = g.state.get_investigator("player")
        _add_asset_to_play(g, "a1", "wooden_sledge", cost=1, traits=["item", "expedition"])
        _add_asset_to_play(g, "a2", "miasmic_crystal", cost=3, traits=["item", "relic", "expedition"])
        _add_asset_to_play(g, "a3", "knife", cost=1, traits=["item", "weapon"])
        loc = g.state.locations["test_location"]
        ctx, pending, _, _ = _apply(g, ctrl, ChaosTokenType.TABLET)
        assert ctx.amount == -3
        _fail(g, ctrl, pending)
        # 自动选费用最低的 Expedition 支援
        assert "a1" not in inv.play_area
        assert "a1" in loc.attachments
        assert g.state.cards_in_play["a1"].attached_to == "test_location"
        # 非 Expedition / 更贵的支援不受影响
        assert "a2" in inv.play_area
        assert "a3" in inv.play_area

    def test_elder_thing_fail_moves_elder_thing_toward_you(self):
        g, ctrl = _make_game("to_the_forbidden_peaks")
        g.state.locations["test_location"].card_data.connections = ["loc_b"]
        _add_location(g, "loc_b", connections=["test_location"])
        _add_enemy(g, "e1", "constricting_elder_thing", ["elder_thing"], location="loc_b")
        ctx, pending, _, _ = _apply(g, ctrl, ChaosTokenType.ELDER_THING)
        assert ctx.amount == -4
        _fail(g, ctrl, pending)
        assert "e1" in g.state.locations["test_location"].enemies
        assert "e1" not in g.state.locations["loc_b"].enemies

    def test_elder_thing_fail_engaged_enemy_attacks(self):
        g, ctrl = _make_game("to_the_forbidden_peaks")
        _add_enemy(g, "e1", "constricting_elder_thing", ["elder_thing"], engaged=True)
        inv = g.state.get_investigator("player")
        inv.damage = 0
        inv.horror = 0
        _, pending, _, _ = _apply(g, ctrl, ChaosTokenType.ELDER_THING)
        _fail(g, ctrl, pending)
        assert inv.damage == 1  # make_enemy_data 默认 1伤害/1恐惧
        assert inv.horror == 1


class TestCityOfTheElderThingsTokens:
    def test_skull_is_keys_controlled(self):
        g, ctrl = _make_game("city_of_the_elder_things")
        g.state.scenario.vars["keys_controlled"] = {"player": 2}
        ctx, *_ = _apply(g, ctrl, ChaosTokenType.SKULL)
        assert ctx.amount == -2

    def test_skull_hard_adds_2(self):
        g, ctrl = _make_game("city_of_the_elder_things")
        _hard(g)
        g.state.scenario.vars["keys_controlled"] = {"player": 2}
        ctx, *_ = _apply(g, ctrl, ChaosTokenType.SKULL)
        assert ctx.amount == -4

    def test_cultist_fail_places_key_on_location(self):
        g, ctrl = _make_game("city_of_the_elder_things")
        g.state.scenario.vars["keys_controlled"] = {"player": 2}
        ctx, pending, _, _ = _apply(g, ctrl, ChaosTokenType.CULTIST)
        assert ctx.amount == -2
        _fail(g, ctrl, pending)
        assert g.state.scenario.vars["keys_controlled"]["player"] == 1
        assert g.state.scenario.vars["keys_on_locations"]["test_location"] == 1

    def test_cultist_hard_places_key_immediately(self):
        g, ctrl = _make_game("city_of_the_elder_things")
        _hard(g)
        g.state.scenario.vars["keys_controlled"] = {"player": 1}
        ctx, pending, _, _ = _apply(g, ctrl, ChaosTokenType.CULTIST)
        assert ctx.amount == -2
        assert g.state.scenario.vars["keys_controlled"]["player"] == 0
        assert g.state.scenario.vars["keys_on_locations"]["test_location"] == 1
        assert not pending  # 无条件效果：无延迟结算

    def test_tablet_no_frost_is_minus3(self):
        g, ctrl = _make_game("city_of_the_elder_things")
        ctx, *_ = _apply(g, ctrl, ChaosTokenType.TABLET)
        assert ctx.amount == -3
        assert not ctx.extra.get("force_auto_fail")

    def test_tablet_frost_revealed_auto_fail_standard(self):
        g, ctrl = _make_game("city_of_the_elder_things")
        ctx, *_ = _apply(g, ctrl, ChaosTokenType.TABLET, extra={"frost_revealed": True})
        assert ctx.extra.get("force_auto_fail") is True
        assert ctx.amount == 0  # 改为自动失败，不取 -3

    def test_tablet_frost_revealed_hard_takes_damage(self):
        g, ctrl = _make_game("city_of_the_elder_things")
        _hard(g)
        inv = g.state.get_investigator("player")
        inv.damage = 0
        ctx, *_ = _apply(g, ctrl, ChaosTokenType.TABLET, extra={"frost_revealed": True})
        assert ctx.extra.get("force_auto_fail") is True
        assert inv.damage == 1

    def test_elder_thing_fail_nearest_enemy_moves(self):
        g, ctrl = _make_game("city_of_the_elder_things")
        g.state.locations["test_location"].card_data.connections = ["loc_b"]
        _add_location(g, "loc_b", connections=["test_location"])
        _add_enemy(g, "e1", "benign_elder_thing", ["elder_thing"], location="loc_b")
        ctx, pending, _, _ = _apply(g, ctrl, ChaosTokenType.ELDER_THING)
        assert ctx.amount == -4
        _fail(g, ctrl, pending)
        assert "e1" in g.state.locations["test_location"].enemies

    def test_elder_thing_fail_engaged_enemy_attacks(self):
        g, ctrl = _make_game("city_of_the_elder_things")
        _hard(g)
        _add_enemy(g, "e1", "reawakened_elder_thing", ["elder_thing"], engaged=True)
        inv = g.state.get_investigator("player")
        inv.damage = 0
        ctx, pending, _, _ = _apply(g, ctrl, ChaosTokenType.ELDER_THING)
        assert ctx.amount == -5
        _fail(g, ctrl, pending)
        assert inv.damage == 1


class TestHeartOfMadnessTokens:
    def test_skull_no_ancient_one(self):
        g, ctrl = _make_game("the_heart_of_madness_part_1")
        ctx, *_ = _apply(g, ctrl, ChaosTokenType.SKULL)
        assert ctx.amount == -1

    def test_skull_ancient_one_at_location(self):
        g, ctrl = _make_game("the_heart_of_madness_part_1")
        _add_enemy(g, "e1", "the_nameless_madness", ["ancient_one", "elite"])
        ctx, *_ = _apply(g, ctrl, ChaosTokenType.SKULL)
        assert ctx.amount == -3

    def test_skull_hard_with_ancient_one(self):
        g, ctrl = _make_game("the_heart_of_madness_part_1")
        _hard(g)
        _add_enemy(g, "e1", "the_nameless_madness", ["ancient_one", "elite"], engaged=True)
        ctx, *_ = _apply(g, ctrl, ChaosTokenType.SKULL)
        assert ctx.amount == -4

    def test_cultist_plain_is_minus1(self):
        g, ctrl = _make_game("the_heart_of_madness_part_1")
        ctx, *_ = _apply(g, ctrl, ChaosTokenType.CULTIST)
        assert ctx.amount == -1
        assert not ctx.extra.get("treat_token_as_frost")

    def test_cultist_at_mist_pylon_treated_as_frost(self):
        g, ctrl = _make_game("the_heart_of_madness_part_1")
        _add_location(g, "mist_pylon_a")
        inv = g.state.get_investigator("player")
        inv.location_id = "mist_pylon_a"
        ctx, *_ = _apply(g, ctrl, ChaosTokenType.CULTIST)
        assert ctx.amount == -1  # frost 同为 -1，修正不变
        assert ctx.extra.get("treat_token_as_frost") is True

    def test_tablet_fail_draws_tekeli_li(self):
        g, ctrl = _make_game("the_heart_of_madness_part_1")
        _set_tekeli_li(g, ["tekeli_li_a"])
        inv = g.state.get_investigator("player")
        inv.hand = []
        ctx, pending, _, _ = _apply(g, ctrl, ChaosTokenType.TABLET)
        assert ctx.amount == -3
        _fail(g, ctrl, pending)
        assert inv.hand == ["tekeli_li_a"]
        assert g.state.scenario.vars["tekeli_li_deck"] == []

    def test_tablet_hard_draws_immediately(self):
        g, ctrl = _make_game("the_heart_of_madness_part_1")
        _hard(g)
        _set_tekeli_li(g, ["tekeli_li_a"])
        inv = g.state.get_investigator("player")
        inv.hand = []
        ctx, pending, _, _ = _apply(g, ctrl, ChaosTokenType.TABLET)
        assert ctx.amount == -3
        assert inv.hand == ["tekeli_li_a"]  # 无条件效果，立即结算
        assert not pending

    def test_elder_thing_fail_by_3_dooms_agenda(self):
        g, ctrl = _make_game("the_heart_of_madness_part_1")
        g.state.scenario.doom_on_agenda = 0
        ctx, pending, _, _ = _apply(g, ctrl, ChaosTokenType.ELDER_THING)
        assert ctx.amount == -4
        _fail(g, ctrl, pending, difficulty=5, modified_skill=2)  # 失败3点
        assert g.state.scenario.doom_on_agenda == 1

    def test_elder_thing_fail_by_less_than_3_no_doom(self):
        g, ctrl = _make_game("the_heart_of_madness_part_1")
        g.state.scenario.doom_on_agenda = 0
        _, pending, _, _ = _apply(g, ctrl, ChaosTokenType.ELDER_THING)
        _fail(g, ctrl, pending, difficulty=3, modified_skill=1)  # 失败2点
        assert g.state.scenario.doom_on_agenda == 0

    def test_elder_thing_hard_is_minus5(self):
        g, ctrl = _make_game("the_heart_of_madness_part_1")
        _hard(g)
        ctx, *_ = _apply(g, ctrl, ChaosTokenType.ELDER_THING)
        assert ctx.amount == -5


class TestInterludesAndFrost:
    def test_endless_night_has_no_token_effects(self):
        g, ctrl = _make_game("endless_night")
        ctx, pending, success_pending, handled = _apply(g, ctrl, ChaosTokenType.SKULL)
        assert handled is False
        assert ctx.amount == 0
        assert not pending and not success_pending

    def test_final_night_has_no_token_effects(self):
        g, ctrl = _make_game("final_night")
        ctx, *_ , handled = _apply(g, ctrl, ChaosTokenType.CULTIST)
        assert handled is False
        assert ctx.amount == 0

    def test_frost_token_has_no_scenario_branch(self):
        # EOE 全部剧本 frost 固定 -1（引擎按 CHAOS_TOKEN_VALUES 处理），无剧本分支
        g, ctrl = _make_game("ice_and_death_part_2")
        ctx, pending, success_pending, handled = _apply(g, ctrl, ChaosTokenType.FROST)
        assert handled is False
        assert ctx.amount == 0
        assert not pending and not success_pending

    def test_non_eoe_scenario_not_handled(self):
        g, ctrl = _make_game("the_gathering")
        ctx, *_ , handled = _apply(g, ctrl, ChaosTokenType.SKULL)
        assert handled is False
