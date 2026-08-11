"""Tests for The Circle Undone (TCU) scenario chaos token effects.

直接测 tokens_tcu.apply_token / on_fail / on_success（模块尚未接入事件总线，
由主代理统一接线），不走 controller 的事件发射路径。
"""

from backend.engine.event_bus import EventContext
from backend.models.enums import CardType, ChaosTokenType, GameEvent, Skill
from backend.models.state import CardData
from backend.scenarios import tokens_tcu
from backend.tests.conftest import make_enemy_data, make_location_data
from backend.tests.test_scenario_tokens import _add_enemy, _make_game


def _apply(game, ctrl, token, **ctx_kw):
    """构造 CHAOS_TOKEN_RESOLVED ctx 并直接调用 apply_token。"""
    inv = game.state.get_investigator("player")
    ctx = EventContext(
        game_state=game.state, event=GameEvent.CHAOS_TOKEN_RESOLVED,
        investigator_id="player", chaos_token=token, amount=0, **ctx_kw,
    )
    pending = ctrl._token_pending.setdefault("player", set())
    success_pending = ctrl._token_success_pending.setdefault("player", set())
    handled = tokens_tcu.apply_token(ctrl, ctx, inv, pending, success_pending)
    assert handled
    return ctx, pending, success_pending


def _fail(game, ctrl, pending, **ctx_kw):
    """构造 SKILL_TEST_FAILED ctx 并直接调用 on_fail。"""
    ctx = EventContext(
        game_state=game.state, event=GameEvent.SKILL_TEST_FAILED,
        investigator_id="player", success=False, **ctx_kw,
    )
    tokens_tcu.on_fail(ctrl, ctx, pending)
    return ctx


def _hard(game):
    game.state.scenario.vars["difficulty"] = "hard"


def _haunt(game, *location_ids):
    game.state.scenario.vars["haunted_locations"] = set(location_ids)


def _haunted_count(game):
    return int(game.state.scenario.vars.get("haunted_abilities_resolved", 0) or 0)


def _add_location(game, location_id, connections):
    data = make_location_data(id=location_id, connections=connections)
    game.register_card_data(data)
    game.add_location(location_id, data, clues=0)
    return game.state.locations[location_id]


def _add_treachery(game, card_id):
    game.register_card_data(CardData(
        id=card_id, name=card_id, name_cn=f"诡计{card_id}", type=CardType.TREACHERY,
    ))


class TestInterface:
    def test_non_tcu_scenario_not_handled(self):
        g, ctrl = _make_game("the_gathering")
        inv = g.state.get_investigator("player")
        ctx = EventContext(
            game_state=g.state, event=GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="player", chaos_token=ChaosTokenType.SKULL, amount=0,
        )
        assert tokens_tcu.apply_token(ctrl, ctx, inv, set(), set()) is False

    def test_numeric_token_handled_noop(self):
        g, ctrl = _make_game("the_witching_hour")
        ctx, pending, _ = _apply(g, ctrl, ChaosTokenType.MINUS_2)
        assert ctx.amount == 0
        assert not pending

    def test_on_success_noop(self):
        g, ctrl = _make_game("the_witching_hour")
        tokens_tcu.on_success(ctrl, None, {"anything"})  # 不抛异常


class TestWitchingHourTokens:
    def test_skull_standard_margin_discard_on_fail(self):
        g, ctrl = _make_game("the_witching_hour")
        g.state.scenario.encounter_deck = ["a", "b", "c", "d", "e"]
        ctx, pending, _ = _apply(g, ctrl, ChaosTokenType.SKULL)
        assert ctx.amount == -1
        assert g.state.scenario.encounter_deck == ["a", "b", "c", "d", "e"]
        _fail(g, ctrl, pending, difficulty=4, modified_skill=1)
        assert g.state.scenario.encounter_deck == ["d", "e"]
        assert g.state.scenario.encounter_discard == ["a", "b", "c"]

    def test_skull_hard_discards_test_difficulty_immediately(self):
        g, ctrl = _make_game("the_witching_hour")
        _hard(g)
        g.state.scenario.encounter_deck = ["a", "b", "c", "d"]
        ctx, pending, _ = _apply(g, ctrl, ChaosTokenType.SKULL, difficulty=3)
        assert ctx.amount == -2
        assert g.state.scenario.encounter_deck == ["d"]
        assert g.state.scenario.encounter_discard == ["a", "b", "c"]

    def test_tablet_draws_bottommost_treachery_on_fail(self):
        g, ctrl = _make_game("the_witching_hour")
        _add_treachery(g, "tr_bottom")
        _add_treachery(g, "tr_top")
        g.register_card_data(make_enemy_data(id="some_enemy"))
        # 弃牌堆底 = 列表索引 0；底部是敌人则跳过，抽到底部第一张诡计
        g.state.scenario.encounter_discard = ["some_enemy", "tr_bottom", "tr_top"]
        ctx, pending, _ = _apply(g, ctrl, ChaosTokenType.TABLET)
        assert ctx.amount == -1
        _fail(g, ctrl, pending)
        assert g.state.scenario.encounter_discard == ["some_enemy", "tr_top"]

    def test_tablet_hard_no_treachery_in_discard(self):
        g, ctrl = _make_game("the_witching_hour")
        _hard(g)
        g.state.scenario.encounter_discard = []
        ctx, pending, _ = _apply(g, ctrl, ChaosTokenType.TABLET)
        assert ctx.amount == -2
        _fail(g, ctrl, pending)  # 无诡计可抽，不抛异常
        assert g.state.scenario.encounter_discard == []

    def test_elder_standard_readies_and_heals_least_damaged_witch(self):
        g, ctrl = _make_game("the_witching_hour")
        _add_location(g, "loc2", ["test_location"])
        g.state.locations["test_location"].card_data.connections = ["loc2"]
        witch_a = _add_enemy(g, "e1", "priestess_of_the_coven", ["witch"])  # damage 2, exhausted
        witch_a.exhausted = True
        witch_a.damage = 2
        witch_b = _add_enemy(g, "e2", "coven_initiate", ["witch"], location="loc2")  # damage 1
        witch_b.damage = 1
        witch_c = _add_enemy(g, "e3", "anette_mason", ["witch", "elite"])  # ready 无伤害：不合格
        ctx, pending, _ = _apply(g, ctrl, ChaosTokenType.ELDER_THING)
        assert ctx.amount == -3
        _fail(g, ctrl, pending)
        # 自动选对玩家最有利（伤害最低）的 witch_b：治愈+准备
        assert witch_b.damage == 0 and not witch_b.exhausted
        assert witch_a.damage == 2 and witch_a.exhausted  # 未动
        assert witch_c.damage == 0 and not witch_c.exhausted  # 未动

    def test_elder_hard_readies_and_heals_all_witches_nearby(self):
        g, ctrl = _make_game("the_witching_hour")
        _hard(g)
        _add_location(g, "loc2", ["test_location"])
        g.state.locations["test_location"].card_data.connections = ["loc2"]
        witch_a = _add_enemy(g, "e1", "priestess_of_the_coven", ["witch"])
        witch_a.exhausted = True
        witch_a.damage = 2
        witch_b = _add_enemy(g, "e2", "coven_initiate", ["witch"], location="loc2")
        witch_b.damage = 1
        far = _add_enemy(g, "e3", "vengeful_witch", ["witch"])  # 远处不相连
        _add_location(g, "loc3", [])
        g.state.locations["loc3"].enemies.append("e3")
        g.state.locations["test_location"].enemies.remove("e3")
        far.damage = 3
        ctx, pending, _ = _apply(g, ctrl, ChaosTokenType.ELDER_THING)
        assert ctx.amount == -4
        _fail(g, ctrl, pending)
        assert witch_a.damage == 0 and not witch_a.exhausted
        assert witch_b.damage == 0 and not witch_b.exhausted
        assert far.damage == 3  # 不相连，未受影响


class TestAtDeathsDoorstepTokens:
    def test_skull_scales_with_haunted(self):
        g, ctrl = _make_game("at_deaths_doorstep")
        ctx, _, _ = _apply(g, ctrl, ChaosTokenType.SKULL)
        assert ctx.amount == -1
        _haunt(g, "test_location")
        ctx, _, _ = _apply(g, ctrl, ChaosTokenType.SKULL)
        assert ctx.amount == -3

    def test_skull_hard_scales_with_haunted(self):
        g, ctrl = _make_game("at_deaths_doorstep")
        _hard(g)
        ctx, _, _ = _apply(g, ctrl, ChaosTokenType.SKULL)
        assert ctx.amount == -2
        _haunt(g, "test_location")
        ctx, _, _ = _apply(g, ctrl, ChaosTokenType.SKULL)
        assert ctx.amount == -4

    def test_tablet_standard_attack_fail_resolves_haunted(self):
        g, ctrl = _make_game("at_deaths_doorstep")
        _haunt(g, "test_location")
        ctx, pending, _ = _apply(g, ctrl, ChaosTokenType.TABLET, skill_type=Skill.COMBAT)
        assert ctx.amount == -2
        assert _haunted_count(g) == 0  # 普通面需失败才结算
        _fail(g, ctrl, pending)
        assert _haunted_count(g) == 1

    def test_tablet_standard_non_attack_no_haunted(self):
        g, ctrl = _make_game("at_deaths_doorstep")
        _haunt(g, "test_location")
        ctx, pending, _ = _apply(g, ctrl, ChaosTokenType.TABLET, skill_type=Skill.INTELLECT)
        assert ctx.amount == -2
        _fail(g, ctrl, pending)
        assert _haunted_count(g) == 0

    def test_tablet_hard_attack_resolves_immediately(self):
        g, ctrl = _make_game("at_deaths_doorstep")
        _hard(g)
        _haunt(g, "test_location")
        ctx, pending, _ = _apply(g, ctrl, ChaosTokenType.TABLET, skill_type=Skill.AGILITY)
        assert ctx.amount == -3
        assert _haunted_count(g) == 1  # 困难面无需失败
        _fail(g, ctrl, pending)
        assert _haunted_count(g) == 1

    def test_elder_thing_spectral_damage(self):
        g, ctrl = _make_game("at_deaths_doorstep")
        _add_enemy(g, "e1", "nether_mist", ["monster", "spectral"])
        inv = g.state.get_investigator("player")
        ctx, _, _ = _apply(g, ctrl, ChaosTokenType.ELDER_THING)
        assert ctx.amount == -2
        assert inv.damage == 1 and inv.horror == 0

    def test_elder_thing_hard_spectral_damage_and_horror(self):
        g, ctrl = _make_game("at_deaths_doorstep")
        _hard(g)
        _add_enemy(g, "e1", "wraith", ["monster", "spectral"], engaged=True)
        inv = g.state.get_investigator("player")
        ctx, _, _ = _apply(g, ctrl, ChaosTokenType.ELDER_THING)
        assert ctx.amount == -4
        assert inv.damage == 1 and inv.horror == 1

    def test_elder_thing_no_spectral(self):
        g, ctrl = _make_game("at_deaths_doorstep")
        _add_enemy(g, "e1", "coven_initiate", ["witch"])
        inv = g.state.get_investigator("player")
        ctx, _, _ = _apply(g, ctrl, ChaosTokenType.ELDER_THING)
        assert ctx.amount == -2
        assert inv.damage == 0 and inv.horror == 0


class TestSecretNameTokens:
    def test_skull_extradimensional(self):
        g, ctrl = _make_game("the_secret_name")
        ctx, _, _ = _apply(g, ctrl, ChaosTokenType.SKULL)
        assert ctx.amount == -1
        g.state.locations["test_location"].card_data.traits = ["extradimensional"]
        ctx, _, _ = _apply(g, ctrl, ChaosTokenType.SKULL)
        assert ctx.amount == -3
        g.state.locations["test_location"].card_data.traits = ["異次元"]
        ctx, _, _ = _apply(g, ctrl, ChaosTokenType.SKULL)
        assert ctx.amount == -3

    def test_skull_hard_extradimensional(self):
        g, ctrl = _make_game("the_secret_name")
        _hard(g)
        ctx, _, _ = _apply(g, ctrl, ChaosTokenType.SKULL)
        assert ctx.amount == -2
        g.state.locations["test_location"].card_data.traits = ["異次元"]
        ctx, _, _ = _apply(g, ctrl, ChaosTokenType.SKULL)
        assert ctx.amount == -4

    def test_cultist_reveals_another_and_discards_on_fail(self):
        g, ctrl = _make_game("the_secret_name")
        g.chaos_bag.tokens = [ChaosTokenType.MINUS_3]
        g.state.scenario.encounter_deck = ["a", "b", "c", "d"]
        ctx, pending, _ = _apply(g, ctrl, ChaosTokenType.CULTIST)
        assert ctx.amount == -3  # 本身0 + 额外标记-3
        _fail(g, ctrl, pending)
        assert g.state.scenario.encounter_deck == ["d"]

    def test_cultist_hard_discards_5_on_fail(self):
        g, ctrl = _make_game("the_secret_name")
        _hard(g)
        g.chaos_bag.tokens = [ChaosTokenType.MINUS_1]
        g.state.scenario.encounter_deck = ["a", "b", "c", "d", "e", "f"]
        ctx, pending, _ = _apply(g, ctrl, ChaosTokenType.CULTIST)
        assert ctx.amount == -1
        _fail(g, ctrl, pending)
        assert g.state.scenario.encounter_deck == ["f"]

    def test_tablet_nahab_attacks_only_at_your_location_standard(self):
        g, ctrl = _make_game("the_secret_name")
        inv = g.state.get_investigator("player")
        _add_location(g, "loc2", ["test_location"])
        nahab = _add_enemy(g, "e1", "nahab", ["monster", "witch", "elite"], location="loc2")
        ctx, pending, _ = _apply(g, ctrl, ChaosTokenType.TABLET)
        assert ctx.amount == -2
        _fail(g, ctrl, pending)
        assert inv.damage == 0 and inv.horror == 0  # 娜哈布不在你所在地，不攻击

        # 交战（即在你所在地）时攻击
        g.state.locations["loc2"].enemies.remove("e1")
        inv.threat_area.append("e1")
        ctx, pending, _ = _apply(g, ctrl, ChaosTokenType.TABLET)
        _fail(g, ctrl, pending)
        assert inv.damage == 1 and inv.horror == 1

    def test_tablet_hard_nahab_attacks_regardless_of_location(self):
        g, ctrl = _make_game("the_secret_name")
        _hard(g)
        inv = g.state.get_investigator("player")
        _add_location(g, "loc2", ["test_location"])
        _add_enemy(g, "e1", "nahab", ["monster", "witch", "elite"], location="loc2")
        ctx, pending, _ = _apply(g, ctrl, ChaosTokenType.TABLET)
        assert ctx.amount == -3
        _fail(g, ctrl, pending)
        assert inv.damage == 1 and inv.horror == 1

    def test_elder_thing_standard_hunters_on_fail(self):
        g, ctrl = _make_game("the_secret_name")
        inv = g.state.get_investigator("player")
        _add_location(g, "loc2", ["test_location"])
        g.state.locations["test_location"].card_data.connections = ["loc2"]
        _add_enemy(g, "e1", "hunter_x", ["monster", "hunter"], location="loc2")
        ctx, pending, _ = _apply(g, ctrl, ChaosTokenType.ELDER_THING)
        assert ctx.amount == -3
        assert "e1" in g.state.locations["loc2"].enemies  # 普通面需失败才移动
        _fail(g, ctrl, pending)
        assert "e1" in inv.threat_area  # 猎手走一步进入所在地并交战

    def test_elder_thing_hard_hunters_immediately(self):
        g, ctrl = _make_game("the_secret_name")
        _hard(g)
        inv = g.state.get_investigator("player")
        _add_location(g, "loc2", ["test_location"])
        g.state.locations["test_location"].card_data.connections = ["loc2"]
        _add_enemy(g, "e1", "hunter_x", ["monster", "hunter"], location="loc2")
        ctx, pending, _ = _apply(g, ctrl, ChaosTokenType.ELDER_THING)
        assert ctx.amount == -4
        assert "e1" in inv.threat_area  # 困难面立即结算


class TestWagesOfSinTokens:
    def test_skull_standard_counts_unfinished_business_plus_one(self):
        g, ctrl = _make_game("the_wages_of_sin")
        ctx, _, _ = _apply(g, ctrl, ChaosTokenType.SKULL)
        assert ctx.amount == -1  # 0 + 1
        g.state.scenario.victory_display = ["heretic_a", "heretic_b"]
        ctx, _, _ = _apply(g, ctrl, ChaosTokenType.SKULL)
        assert ctx.amount == -3  # 2 + 1

    def test_skull_hard_counts_and_reveals_another(self):
        g, ctrl = _make_game("the_wages_of_sin")
        _hard(g)
        g.chaos_bag.tokens = [ChaosTokenType.MINUS_4]
        g.state.scenario.victory_display = ["heretic_a", "unfinished_business"]
        ctx, _, _ = _apply(g, ctrl, ChaosTokenType.SKULL)
        assert ctx.amount == -6  # -2 + 额外标记-4

    def test_cultist_heretic_buff_logged(self):
        g, ctrl = _make_game("the_wages_of_sin")
        g.state.scenario.round_number = 5
        ctx, _, _ = _apply(g, ctrl, ChaosTokenType.CULTIST)
        assert ctx.amount == -3
        assert g.state.scenario.vars["wos_heretic_buff_round"] == 5

    def test_cultist_hard(self):
        g, ctrl = _make_game("the_wages_of_sin")
        _hard(g)
        ctx, _, _ = _apply(g, ctrl, ChaosTokenType.CULTIST)
        assert ctx.amount == -4

    def test_tablet_triggers_unfinished_business_on_fail(self):
        g, ctrl = _make_game("the_wages_of_sin")
        _add_enemy(g, "e1", "heretic_a", ["witch", "spectral"], engaged=True)
        ctx, pending, _ = _apply(g, ctrl, ChaosTokenType.TABLET)
        assert ctx.amount == -3
        _fail(g, ctrl, pending)
        assert g.state.scenario.vars.get("wos_ub_forced_triggered") == 1

    def test_tablet_hard_no_unfinished_business(self):
        g, ctrl = _make_game("the_wages_of_sin")
        _hard(g)
        ctx, pending, _ = _apply(g, ctrl, ChaosTokenType.TABLET)
        assert ctx.amount == -4
        _fail(g, ctrl, pending)
        assert not g.state.scenario.vars.get("wos_ub_forced_triggered")

    def test_elder_thing_standard_attack_fail_resolves_haunted(self):
        g, ctrl = _make_game("the_wages_of_sin")
        _haunt(g, "test_location")
        ctx, pending, _ = _apply(g, ctrl, ChaosTokenType.ELDER_THING, skill_type=Skill.COMBAT)
        assert ctx.amount == -2
        assert _haunted_count(g) == 0
        _fail(g, ctrl, pending)
        assert _haunted_count(g) == 1

    def test_elder_thing_hard_attack_resolves_immediately(self):
        g, ctrl = _make_game("the_wages_of_sin")
        _hard(g)
        _haunt(g, "test_location")
        ctx, _, _ = _apply(g, ctrl, ChaosTokenType.ELDER_THING, skill_type=Skill.AGILITY)
        assert ctx.amount == -2
        assert _haunted_count(g) == 1


class TestForTheGreaterGoodTokens:
    def test_skull_standard_max_cultist_doom(self):
        g, ctrl = _make_game("for_the_greater_good")
        e1 = _add_enemy(g, "e1", "lodge_neophyte", ["cultist"])
        e1.doom = 2
        e2 = _add_enemy(g, "e2", "keeper_of_secrets", ["cultist"])
        e2.doom = 1
        e3 = _add_enemy(g, "e3", "summoned_beast", ["monster"])
        e3.doom = 4  # 非異教徒，不计
        ctx, _, _ = _apply(g, ctrl, ChaosTokenType.SKULL)
        assert ctx.amount == -2

    def test_skull_hard_total_cultist_doom(self):
        g, ctrl = _make_game("for_the_greater_good")
        _hard(g)
        e1 = _add_enemy(g, "e1", "lodge_neophyte", ["cultist"])
        e1.doom = 2
        e2 = _add_enemy(g, "e2", "keeper_of_secrets", ["cultist"])
        e2.doom = 1
        e3 = _add_enemy(g, "e3", "summoned_beast", ["monster"])
        e3.doom = 4
        ctx, _, _ = _apply(g, ctrl, ChaosTokenType.SKULL)
        assert ctx.amount == -3

    def test_cultist_reveals_another_both_faces(self):
        for hard in (False, True):
            g, ctrl = _make_game("for_the_greater_good")
            if hard:
                _hard(g)
            g.chaos_bag.tokens = [ChaosTokenType.MINUS_3]
            ctx, _, _ = _apply(g, ctrl, ChaosTokenType.CULTIST)
            assert ctx.amount == -5  # -2 + 额外-3

    def test_tablet_standard_nearest_cultist_doom_on_fail(self):
        g, ctrl = _make_game("for_the_greater_good")
        near = _add_enemy(g, "e1", "lodge_neophyte", ["cultist"], engaged=True)
        far = _add_enemy(g, "e2", "keeper_of_secrets", ["cultist"])
        ctx, pending, _ = _apply(g, ctrl, ChaosTokenType.TABLET)
        assert ctx.amount == -3
        _fail(g, ctrl, pending)
        assert near.doom == 1 and far.doom == 0

    def test_tablet_hard_each_cultist_doom_on_fail(self):
        g, ctrl = _make_game("for_the_greater_good")
        _hard(g)
        e1 = _add_enemy(g, "e1", "lodge_neophyte", ["cultist"], engaged=True)
        e2 = _add_enemy(g, "e2", "keeper_of_secrets", ["cultist"])
        ctx, pending, _ = _apply(g, ctrl, ChaosTokenType.TABLET)
        assert ctx.amount == -3
        _fail(g, ctrl, pending)
        assert e1.doom == 1 and e2.doom == 1

    def test_tablet_hard_no_cultists_logs_only(self):
        g, ctrl = _make_game("for_the_greater_good")
        _hard(g)
        ctx, pending, _ = _apply(g, ctrl, ChaosTokenType.TABLET)
        _fail(g, ctrl, pending)
        assert any("再揭示" in m for m in g.state.effect_log)

    def test_elder_standard_moves_1_doom_to_agenda(self):
        g, ctrl = _make_game("for_the_greater_good")
        e1 = _add_enemy(g, "e1", "lodge_neophyte", ["cultist"], engaged=True)
        e1.doom = 2
        ctx, pending, _ = _apply(g, ctrl, ChaosTokenType.ELDER_THING)
        assert ctx.amount == -3
        _fail(g, ctrl, pending)
        assert e1.doom == 1
        assert g.state.scenario.doom_on_agenda == 1

    def test_elder_hard_moves_all_doom_from_most_doomed(self):
        g, ctrl = _make_game("for_the_greater_good")
        _hard(g)
        e1 = _add_enemy(g, "e1", "lodge_neophyte", ["cultist"], engaged=True)
        e1.doom = 1
        e2 = _add_enemy(g, "e2", "keeper_of_secrets", ["cultist"])
        e2.doom = 2
        ctx, pending, _ = _apply(g, ctrl, ChaosTokenType.ELDER_THING)
        _fail(g, ctrl, pending)
        assert e1.doom == 1 and e2.doom == 0
        assert g.state.scenario.doom_on_agenda == 2

    def test_elder_hard_no_doomed_cultist_logs_only(self):
        g, ctrl = _make_game("for_the_greater_good")
        _hard(g)
        _add_enemy(g, "e1", "lodge_neophyte", ["cultist"])
        ctx, pending, _ = _apply(g, ctrl, ChaosTokenType.ELDER_THING)
        _fail(g, ctrl, pending)
        assert g.state.scenario.doom_on_agenda == 0
        assert any("再揭示" in m for m in g.state.effect_log)


class TestUnionAndDisillusionTokens:
    def test_skull_circle_reveals_another(self):
        g, ctrl = _make_game("union_and_disillusion")
        g.chaos_bag.tokens = [ChaosTokenType.MINUS_2]
        ctx, _, _ = _apply(g, ctrl, ChaosTokenType.SKULL)
        assert ctx.amount == -2  # 非 circle 不再揭示
        ctx, _, _ = _apply(g, ctrl, ChaosTokenType.SKULL, extra={"circle_action": True})
        assert ctx.amount == -4  # -2 + 额外-2

    def test_skull_hard_circle(self):
        g, ctrl = _make_game("union_and_disillusion")
        _hard(g)
        g.chaos_bag.tokens = [ChaosTokenType.MINUS_1]
        ctx, _, _ = _apply(g, ctrl, ChaosTokenType.SKULL, extra={"circle_action": True})
        assert ctx.amount == -4  # -3 + 额外-1

    def test_cultist_damage_and_horror_when_none(self):
        g, ctrl = _make_game("union_and_disillusion")
        inv = g.state.get_investigator("player")
        inv.damage = 0
        inv.horror = 0
        ctx, _, _ = _apply(g, ctrl, ChaosTokenType.CULTIST)
        assert ctx.amount == -3
        assert inv.damage == 1 and inv.horror == 1

    def test_cultist_hard_only_missing_one(self):
        g, ctrl = _make_game("union_and_disillusion")
        _hard(g)
        inv = g.state.get_investigator("player")
        inv.damage = 1
        inv.horror = 0
        ctx, _, _ = _apply(g, ctrl, ChaosTokenType.CULTIST)
        assert ctx.amount == -4
        assert inv.damage == 1 and inv.horror == 1  # 只补恐惧

    def test_tablet_spectral_attacks_even_exhausted(self):
        g, ctrl = _make_game("union_and_disillusion")
        inv = g.state.get_investigator("player")
        sp = _add_enemy(g, "e1", "wraith", ["monster", "spectral"])
        sp.exhausted = True
        g.state.get_card_data("wraith").enemy_damage = 2
        g.state.get_card_data("wraith").enemy_horror = 1
        ctx, pending, _ = _apply(g, ctrl, ChaosTokenType.TABLET)
        assert ctx.amount == -3
        _fail(g, ctrl, pending)
        assert inv.damage == 2 and inv.horror == 1

    def test_tablet_hard_picks_weakest_spectral(self):
        g, ctrl = _make_game("union_and_disillusion")
        _hard(g)
        inv = g.state.get_investigator("player")
        _add_enemy(g, "e1", "wraith", ["monster", "spectral"])
        g.state.get_card_data("wraith").enemy_damage = 3
        g.state.get_card_data("wraith").enemy_horror = 3
        _add_enemy(g, "e2", "nether_mist", ["monster", "spectral"])
        g.state.get_card_data("nether_mist").enemy_damage = 1
        g.state.get_card_data("nether_mist").enemy_horror = 0
        ctx, pending, _ = _apply(g, ctrl, ChaosTokenType.TABLET)
        assert ctx.amount == -4
        _fail(g, ctrl, pending)
        assert inv.damage == 1 and inv.horror == 0  # 自动选最弱者

    def test_tablet_no_spectral_at_location(self):
        g, ctrl = _make_game("union_and_disillusion")
        inv = g.state.get_investigator("player")
        _add_location(g, "loc2", [])
        _add_enemy(g, "e1", "wraith", ["monster", "spectral"], location="loc2")
        ctx, pending, _ = _apply(g, ctrl, ChaosTokenType.TABLET)
        _fail(g, ctrl, pending)
        assert inv.damage == 0 and inv.horror == 0

    def test_elder_thing_circle_fail_resolves_haunted(self):
        g, ctrl = _make_game("union_and_disillusion")
        _haunt(g, "test_location")
        ctx, pending, _ = _apply(
            g, ctrl, ChaosTokenType.ELDER_THING, extra={"circle_action": True})
        assert ctx.amount == -3
        assert _haunted_count(g) == 0
        _fail(g, ctrl, pending)
        assert _haunted_count(g) == 1

    def test_elder_thing_hard_non_circle_no_haunted(self):
        g, ctrl = _make_game("union_and_disillusion")
        _hard(g)
        _haunt(g, "test_location")
        ctx, pending, _ = _apply(g, ctrl, ChaosTokenType.ELDER_THING)
        assert ctx.amount == -4
        _fail(g, ctrl, pending)
        assert _haunted_count(g) == 0


class TestInTheClutchesOfChaosTokens:
    def test_skull_counts_doom_and_breaches(self):
        g, ctrl = _make_game("in_the_clutches_of_chaos")
        g.state.scenario.vars["breaches"] = {"test_location": 2}
        g.state.locations["test_location"].doom = 1
        ctx, _, _ = _apply(g, ctrl, ChaosTokenType.SKULL)
        assert ctx.amount == -3

    def test_skull_hard_plus_one(self):
        g, ctrl = _make_game("in_the_clutches_of_chaos")
        _hard(g)
        g.state.scenario.vars["breaches"] = {"test_location": 2}
        g.state.locations["test_location"].doom = 1
        ctx, _, _ = _apply(g, ctrl, ChaosTokenType.SKULL)
        assert ctx.amount == -4

    def test_cultist_adds_breach_below_3(self):
        g, ctrl = _make_game("in_the_clutches_of_chaos")
        g.chaos_bag.tokens = [ChaosTokenType.MINUS_3]
        g.state.scenario.vars["breaches"] = {"test_location": 2}
        ctx, _, _ = _apply(g, ctrl, ChaosTokenType.CULTIST)
        assert ctx.amount == -3  # 本身0 + 额外标记
        assert g.state.scenario.vars["breaches"]["test_location"] == 3

    def test_cultist_hard_no_breach_at_3(self):
        g, ctrl = _make_game("in_the_clutches_of_chaos")
        _hard(g)
        g.chaos_bag.tokens = [ChaosTokenType.MINUS_1]
        g.state.scenario.vars["breaches"] = {"test_location": 3}
        ctx, _, _ = _apply(g, ctrl, ChaosTokenType.CULTIST)
        assert ctx.amount == -1
        assert g.state.scenario.vars["breaches"]["test_location"] == 3

    def test_tablet_removes_act_breaches_by_margin(self):
        g, ctrl = _make_game("in_the_clutches_of_chaos")
        g.state.scenario.vars["act_breaches"] = 5
        ctx, pending, _ = _apply(g, ctrl, ChaosTokenType.TABLET)
        assert ctx.amount == -2
        _fail(g, ctrl, pending, difficulty=5, modified_skill=2)
        assert g.state.scenario.vars["act_breaches"] == 2

    def test_tablet_hard_caps_at_available_breaches(self):
        g, ctrl = _make_game("in_the_clutches_of_chaos")
        _hard(g)
        g.state.scenario.vars["act_breaches"] = 1
        ctx, pending, _ = _apply(g, ctrl, ChaosTokenType.TABLET)
        assert ctx.amount == -3
        _fail(g, ctrl, pending, difficulty=5, modified_skill=2)
        assert g.state.scenario.vars["act_breaches"] == 0

    def test_elder_thing_places_breach_on_random_location(self):
        g, ctrl = _make_game("in_the_clutches_of_chaos")
        ctx, pending, _ = _apply(g, ctrl, ChaosTokenType.ELDER_THING)
        assert ctx.amount == -3
        _fail(g, ctrl, pending)
        assert g.state.scenario.vars["breaches"] == {"test_location": 1}

    def test_elder_thing_hard(self):
        g, ctrl = _make_game("in_the_clutches_of_chaos")
        _hard(g)
        ctx, pending, _ = _apply(g, ctrl, ChaosTokenType.ELDER_THING)
        assert ctx.amount == -4
        _fail(g, ctrl, pending)
        assert g.state.scenario.vars["breaches"] == {"test_location": 1}


class TestBeforeTheBlackThroneTokens:
    def test_skull_standard_half_doom_rounded_up_min_2(self):
        g, ctrl = _make_game("before_the_black_throne")
        aza = _add_enemy(g, "aza1", "azathoth", ["ancient_one", "elite"])
        aza.doom = 3
        ctx, _, _ = _apply(g, ctrl, ChaosTokenType.SKULL)
        assert ctx.amount == -2  # ceil(3/2)=2
        aza.doom = 5
        ctx, _, _ = _apply(g, ctrl, ChaosTokenType.SKULL)
        assert ctx.amount == -3  # ceil(5/2)=3

    def test_skull_hard_full_doom_min_2(self):
        g, ctrl = _make_game("before_the_black_throne")
        _hard(g)
        aza = _add_enemy(g, "aza1", "azathoth", ["ancient_one", "elite"])
        aza.doom = 5
        ctx, _, _ = _apply(g, ctrl, ChaosTokenType.SKULL)
        assert ctx.amount == -5
        aza.doom = 1
        ctx, _, _ = _apply(g, ctrl, ChaosTokenType.SKULL)
        assert ctx.amount == -2  # 至少2

    def test_skull_no_azathoth_in_play(self):
        g, ctrl = _make_game("before_the_black_throne")
        ctx, _, _ = _apply(g, ctrl, ChaosTokenType.SKULL)
        assert ctx.amount == -2  # 0毁灭 → 最小值2

    def test_cultist_pulls_cultist_enemy_on_fail(self):
        g, ctrl = _make_game("before_the_black_throne")
        g.chaos_bag.tokens = [ChaosTokenType.ZERO]
        g.register_card_data(make_enemy_data(id="lodge_jailor", keywords=["cultist"]))
        g.state.scenario.encounter_deck = ["lodge_jailor"]
        ctx, pending, _ = _apply(g, ctrl, ChaosTokenType.CULTIST)
        assert ctx.amount == 0
        _fail(g, ctrl, pending)
        assert g.state.scenario.encounter_deck == []
        assert any(inst.card_id == "lodge_jailor"
                   for inst in g.state.cards_in_play.values())

    def test_cultist_hard_pulls_from_discard(self):
        g, ctrl = _make_game("before_the_black_throne")
        _hard(g)
        g.chaos_bag.tokens = [ChaosTokenType.ZERO]
        g.register_card_data(make_enemy_data(id="nathan_wick", keywords=["cultist", "elite"]))
        g.state.scenario.encounter_discard = ["nathan_wick"]
        ctx, pending, _ = _apply(g, ctrl, ChaosTokenType.CULTIST)
        _fail(g, ctrl, pending)
        assert g.state.scenario.encounter_discard == []
        assert any(inst.card_id == "nathan_wick"
                   for inst in g.state.cards_in_play.values())

    def test_tablet_azathoth_attacks_on_fail(self):
        g, ctrl = _make_game("before_the_black_throne")
        inv = g.state.get_investigator("player")
        _add_enemy(g, "aza1", "azathoth", ["ancient_one", "elite"])
        g.state.get_card_data("azathoth").enemy_damage = 4
        g.state.get_card_data("azathoth").enemy_horror = 4
        ctx, pending, _ = _apply(g, ctrl, ChaosTokenType.TABLET)
        assert ctx.amount == -2
        _fail(g, ctrl, pending)
        assert inv.damage == 4 and inv.horror == 4

    def test_tablet_hard_no_azathoth(self):
        g, ctrl = _make_game("before_the_black_throne")
        _hard(g)
        inv = g.state.get_investigator("player")
        ctx, pending, _ = _apply(g, ctrl, ChaosTokenType.TABLET)
        assert ctx.amount == -3
        _fail(g, ctrl, pending)
        assert inv.damage == 0 and inv.horror == 0

    def test_elder_thing_doom_when_modified_skill_zero(self):
        g, ctrl = _make_game("before_the_black_throne")
        aza = _add_enemy(g, "aza1", "azathoth", ["ancient_one", "elite"])
        aza.doom = 2
        ctx, _, _ = _apply(g, ctrl, ChaosTokenType.ELDER_THING, modified_skill=0)
        assert ctx.amount == -4
        assert aza.doom == 3

    def test_elder_thing_hard_no_doom_when_skill_positive(self):
        g, ctrl = _make_game("before_the_black_throne")
        _hard(g)
        aza = _add_enemy(g, "aza1", "azathoth", ["ancient_one", "elite"])
        aza.doom = 2
        # 引擎此时不写 modified_skill：回退用基础技能值（测试调查员意志3）
        ctx, _, _ = _apply(g, ctrl, ChaosTokenType.ELDER_THING, skill_type=Skill.WILLPOWER)
        assert ctx.amount == -6
        assert aza.doom == 2
