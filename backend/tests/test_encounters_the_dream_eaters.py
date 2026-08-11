"""Tests for The Dream-Eaters encounter treachery effects."""

from __future__ import annotations

from backend.engine.event_bus import EventContext
from backend.models.enums import CardType, ChaosTokenType, GameEvent, Skill
from backend.models.state import CardData, CardInstance
from backend.scenarios import encounters_the_dream_eaters as tde
from backend.tests.conftest import (
    make_asset_data,
    make_enemy_data,
    make_event_data,
    make_location_data,
    make_skill_data,
)
from backend.tests.test_scenario_tokens import _add_enemy, _make_game


def _mk(scenario_id="beyond_the_gates_of_sleep"):
    return _make_game(scenario_id)


def _fail_bag(g):
    """Force the next skill test to fail (AUTO_FAIL → margin = difficulty)."""
    g.chaos_bag.tokens = [ChaosTokenType.AUTO_FAIL]


def _pass_bag(g):
    g.chaos_bag.tokens = [ChaosTokenType.ZERO]


def _resolve(ctrl, card_id, **kw):
    return tde.resolve_treachery(ctrl, card_id, investigator_id="player", **kw)


def _register_treachery(g, card_id, traits=None):
    g.register_card_data(CardData(id=card_id, name=card_id, name_cn=card_id,
                                  type=CardType.TREACHERY, traits=traits or []))


def _register_asset(g, card_id, cost=0, name=None):
    cd = make_asset_data(id=card_id, cost=cost)
    if name:
        cd.name = name
    g.register_card_data(cd)
    return cd


def _add_asset_instance(g, inv, instance_id, card_id):
    inst = CardInstance(instance_id=instance_id, card_id=card_id,
                        owner_id="player", controller_id="player")
    g.state.cards_in_play[instance_id] = inst
    inv.play_area.append(instance_id)
    return inst


def _round_ends(g, inv_id=None):
    g.event_bus.emit(EventContext(game_state=g.state, event=GameEvent.ROUND_ENDS,
                                  investigator_id=inv_id))


def _move_out(g, inv_id="player", dest="elsewhere"):
    g.event_bus.emit(EventContext(game_state=g.state,
                                  event=GameEvent.MOVE_ACTION_INITIATED,
                                  investigator_id=inv_id, location_id=dest))


def _clue_discovered(g, inv_id="player", location_id="test_location"):
    g.event_bus.emit(EventContext(game_state=g.state, event=GameEvent.CLUE_DISCOVERED,
                                  investigator_id=inv_id, location_id=location_id,
                                  amount=1))


class TestBeyondTheGatesOfSleep:
    def test_lost_in_the_woods_surges_and_punishes_woods_investigator(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        woods = make_location_data(id="enchanted_woods_a", name="Enchanted Woods")
        woods.traits = ["woods"]
        g.register_card_data(woods)
        g.add_location("enchanted_woods_a", woods, clues=1)
        inv.location_id = "enchanted_woods_a"
        inv.card_data.skills.willpower = 1
        inv.actions_remaining = 3
        _fail_bag(g)
        r = _resolve(ctrl, "lost_in_the_woods")
        assert r.get("surge") is True
        assert inv.actions_remaining == 2
        assert inv.horror == 1

    def test_lost_in_the_woods_no_effect_outside_woods(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.actions_remaining = 3
        r = _resolve(ctrl, "lost_in_the_woods")  # test_location 非魔幻森林
        assert r.get("surge") is True
        assert inv.actions_remaining == 3 and inv.horror == 0


class TestWakingNightmareAndSpiders:
    def test_outbreak_records_infestation_test(self):
        g, ctrl = _mk()
        r = _resolve(ctrl, "outbreak")
        assert r["message"] == "outbreak"
        assert g.state.scenario.vars["infestation_test_count"] == 1

    def test_will_of_the_spider_mother_fail_marks_restriction_until_round_end(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.card_data.skills.willpower = 1
        _fail_bag(g)
        _resolve(ctrl, "will_of_the_spider_mother")
        assert g.state.scenario.vars["will_of_the_spider_mother"]["player"] is True
        _round_ends(g)
        assert "player" not in g.state.scenario.vars["will_of_the_spider_mother"]

    def test_will_of_the_spider_mother_success_no_restriction(self):
        g, ctrl = _mk()
        _pass_bag(g)  # 意志3 vs 3 → 成功
        _resolve(ctrl, "will_of_the_spider_mother")
        assert "will_of_the_spider_mother" not in g.state.scenario.vars


class TestLawOfYgiroth:
    def test_enters_hand_with_restriction_marker(self):
        for cid in ("law_of_ygiroth_a", "law_of_ygiroth_b", "law_of_ygiroth_c"):
            g, ctrl = _mk()
            inv = g.state.get_investigator("player")
            r = _resolve(ctrl, cid)
            assert r["message"] == cid
            assert cid in inv.hand
            assert g.state.scenario.vars["law_of_ygiroth"]["player"] == cid

    def test_activate_a_discards_even_cost_card(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.actions_remaining = 3
        _register_asset(g, "even_asset", cost=2)
        inv.hand.append("even_asset")
        _resolve(ctrl, "law_of_ygiroth_a")
        assert tde.activate_discard_law_of_ygiroth(ctrl, "player") is True
        assert inv.actions_remaining == 2
        assert "even_asset" in inv.discard and "law_of_ygiroth_a" in inv.discard
        assert "player" not in g.state.scenario.vars["law_of_ygiroth"]

    def test_activate_a_fails_with_only_odd_cost_cards(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.actions_remaining = 3
        _register_asset(g, "odd_asset", cost=3)
        inv.hand.append("odd_asset")
        _resolve(ctrl, "law_of_ygiroth_a")
        assert tde.activate_discard_law_of_ygiroth(ctrl, "player") is False
        assert "law_of_ygiroth_a" in inv.hand

    def test_activate_b_uses_even_skill_icon_count(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.actions_remaining = 3
        g.register_card_data(make_skill_data(id="two_icons",
                                             skill_icons={"willpower": 1, "wild": 1}))
        inv.hand.append("two_icons")
        _resolve(ctrl, "law_of_ygiroth_b")
        assert tde.activate_discard_law_of_ygiroth(ctrl, "player") is True
        assert "two_icons" in inv.discard

    def test_activate_c_uses_even_title_word_count(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.actions_remaining = 3
        _register_asset(g, "lucky_dice", cost=3, name="Lucky Dice")  # 2 words
        inv.hand.append("lucky_dice")
        _resolve(ctrl, "law_of_ygiroth_c")
        assert tde.activate_discard_law_of_ygiroth(ctrl, "player") is True
        assert "lucky_dice" in inv.discard


class TestWhispersOfHypnos:
    def test_pending_choice_then_skill_penalty_until_round_end(self):
        g, ctrl = _mk()
        r = _resolve(ctrl, "whispers_of_hypnos")
        assert r["pending"] is True
        pc = g.state.scenario.vars["pending_choice"]
        assert pc["investigator_id"] == "player"
        assert {o["id"] for o in pc["options"]} == {"willpower", "intellect", "combat", "agility"}
        g.state.scenario.vars.pop("pending_choice")

        r = _resolve(ctrl, "whispers_of_hypnos", choice="combat")
        assert r["pending"] is False
        assert "combat" in g.state.scenario.vars["whispers_of_hypnos"]["skills"]

        ctx = EventContext(game_state=g.state, event=GameEvent.SKILL_VALUE_DETERMINED,
                           investigator_id="player", skill_type=Skill.COMBAT, amount=0)
        g.event_bus.emit(ctx)
        assert ctx.amount == -2
        # 其他技能不受影响
        ctx2 = EventContext(game_state=g.state, event=GameEvent.SKILL_VALUE_DETERMINED,
                            investigator_id="player", skill_type=Skill.WILLPOWER, amount=0)
        g.event_bus.emit(ctx2)
        assert ctx2.amount == 0

        _round_ends(g)
        assert g.state.scenario.vars["whispers_of_hypnos"]["skills"] == []
        ctx3 = EventContext(game_state=g.state, event=GameEvent.SKILL_VALUE_DETERMINED,
                            investigator_id="player", skill_type=Skill.COMBAT, amount=0)
        g.event_bus.emit(ctx3)
        assert ctx3.amount == 0

    def test_second_copy_cannot_repeat_skill(self):
        g, ctrl = _mk()
        _resolve(ctrl, "whispers_of_hypnos", choice="combat")
        r = _resolve(ctrl, "whispers_of_hypnos")
        options = {o["id"] for o in g.state.scenario.vars["pending_choice"]["options"]}
        assert "combat" not in options
        g.state.scenario.vars.pop("pending_choice")
        _resolve(ctrl, "whispers_of_hypnos", choice="intellect")
        assert set(g.state.scenario.vars["whispers_of_hypnos"]["skills"]) == {"combat", "intellect"}


class TestDreamersCurseSet:
    def test_dreamers_curse_caps_at_three_damage(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.card_data.skills.willpower = 1
        _fail_bag(g)  # margin 5 → cap 3
        _resolve(ctrl, "dreamers_curse")
        assert inv.damage == 3

    def test_somniphobia_caps_at_three_horror(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.card_data.skills.willpower = 1
        _fail_bag(g)
        _resolve(ctrl, "somniphobia")
        assert inv.horror == 3

    def test_deeper_slumber_threat_and_activate(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.actions_remaining = 3
        _resolve(ctrl, "deeper_slumber")
        assert any(g.state.cards_in_play[i].card_id == "deeper_slumber"
                   for i in inv.threat_area)
        assert g.state.scenario.vars["deeper_slumber"]["player"] is True
        assert tde.activate_discard_deeper_slumber(ctrl, "player") is True
        assert inv.actions_remaining == 1
        assert "deeper_slumber" in g.state.scenario.encounter_discard


class TestDreamlandsSet:
    def test_dreamlands_eclipse_flag_cleared_at_round_end(self):
        g, ctrl = _mk()
        _resolve(ctrl, "dreamlands_eclipse")
        assert g.state.scenario.vars.get("dreamlands_eclipse") is True
        _round_ends(g)
        assert "dreamlands_eclipse" not in g.state.scenario.vars

    def test_prismatic_phenomenon_discards_instead_of_clues(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        loc = g.state.get_location("test_location")
        inv.clues = 1
        clues0 = loc.clues
        _resolve(ctrl, "prismatic_phenomenon")
        _clue_discovered(g)
        assert inv.clues == 0  # 撤回刚发现的线索
        assert loc.clues == clues0 + 1
        assert not any(i in g.state.cards_in_play and
                       g.state.cards_in_play[i].card_id == "prismatic_phenomenon"
                       for i in inv.threat_area)
        assert "prismatic_phenomenon" in g.state.scenario.encounter_discard


class TestMergingRealities:
    def test_night_terrors_draws_weaknesses_and_removes_others(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        weak = CardData(id="amnesia", name="Amnesia", name_cn="失忆",
                        type=CardType.TREACHERY, subtype="weakness")
        g.register_card_data(weak)
        _register_treachery(g, "normal_a")
        _register_treachery(g, "normal_b")
        inv.deck = ["normal_a", "amnesia", "normal_b"]
        _resolve(ctrl, "night_terrors")
        g.event_bus.emit(EventContext(game_state=g.state,
                                      event=GameEvent.SKILL_TEST_FAILED,
                                      investigator_id="player", success=False))
        assert "amnesia" in inv.hand
        assert sorted(g.state.scenario.vars["removed_from_game"]) == ["normal_a", "normal_b"]
        assert inv.deck == []

    def test_night_terrors_activate_discards_even_on_failure(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.card_data.skills.willpower = 1
        inv.actions_remaining = 3
        _resolve(ctrl, "night_terrors")
        _fail_bag(g)
        assert tde.activate_discard_night_terrors(ctrl, "player") is True
        assert not any(i in g.state.cards_in_play and
                       g.state.cards_in_play[i].card_id == "night_terrors"
                       for i in inv.threat_area)

    def test_glimpse_fast_discard_takes_damage_and_horror(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        _resolve(ctrl, "glimpse_of_the_underworld")
        assert tde.activate_discard_glimpse(ctrl, "player") is True
        assert inv.damage == 1 and inv.horror == 1
        assert "glimpse_of_the_underworld" in g.state.scenario.encounter_discard

    def test_threads_of_reality_surges_without_assets(self):
        g, ctrl = _mk()
        r = _resolve(ctrl, "threads_of_reality")
        assert r.get("surge") is True

    def test_threads_of_reality_attaches_to_highest_cost_asset(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        _register_asset(g, "cheap", cost=1)
        _register_asset(g, "pricey", cost=3)
        _add_asset_instance(g, inv, "a1", "cheap")
        _add_asset_instance(g, inv, "a2", "pricey")
        r = _resolve(ctrl, "threads_of_reality")
        assert r.get("surge") is None
        rec = g.state.scenario.vars["threads_of_reality"]["player"]
        assert rec["asset"] == "a2"
        assert g.state.cards_in_play[rec["instance_id"]].attached_to == "a2"

    def test_threads_of_reality_activate_discards_an_asset(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.actions_remaining = 3
        _register_asset(g, "cheap", cost=1)
        _register_asset(g, "pricey", cost=3)
        _add_asset_instance(g, inv, "a1", "cheap")
        _add_asset_instance(g, inv, "a2", "pricey")
        _resolve(ctrl, "threads_of_reality")
        assert tde.activate_discard_threads_of_reality(ctrl, "player") is True
        assert "a1" not in inv.play_area  # 自动弃费用最低者
        assert "threads_of_reality" in g.state.scenario.encounter_discard
        assert "player" not in g.state.scenario.vars["threads_of_reality"]


class TestSpidersAndCorsairs:
    def test_sickening_webs_attach_and_activate_discard(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.actions_remaining = 3
        _resolve(ctrl, "sickening_webs")
        assert ctrl.location_attachment_instance("test_location", "sickening_webs")
        _pass_bag(g)  # 战斗3 vs 3 → 成功
        assert tde.activate_sickening_webs(ctrl, "player") is True
        assert ctrl.location_attachment_instance("test_location", "sickening_webs") is None
        assert "sickening_webs" in g.state.scenario.encounter_discard

    def test_hunted_by_corsairs_flag_and_activate(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.actions_remaining = 3
        _resolve(ctrl, "hunted_by_corsairs")
        assert g.state.scenario.vars.get("hunted_by_corsairs") is True
        _pass_bag(g)  # 智力3 vs 4 → ZERO 失败！调高难度核查
        inv.card_data.skills.intellect = 4
        assert tde.activate_hunted_by_corsairs(ctrl, "player") is True
        assert "hunted_by_corsairs" not in g.state.scenario.vars


class TestZoogs:
    def test_zoog_burrow_adds_swarm_cards_on_fail(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.card_data.skills.agility = 1
        e = _add_enemy(g, "e1", "zoog_swarm", ["zoog", "swarming_2"])
        _fail_bag(g)  # margin 3
        _resolve(ctrl, "zoog_burrow")
        assert e.uses.get("swarm") == 3

    def test_zoog_burrow_pulls_zoog_when_none_in_play(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.card_data.skills.agility = 1
        g.register_card_data(make_enemy_data(id="zoog_scout", keywords=["zoog"]))
        _register_treachery(g, "filler")
        g.state.scenario.encounter_deck = ["filler", "zoog_scout"]
        _fail_bag(g)
        _resolve(ctrl, "zoog_burrow")
        spawned = [i for i, inst in g.state.cards_in_play.items()
                   if inst.card_id == "zoog_scout"]
        assert spawned and spawned[0] in inv.threat_area
        assert "zoog_scout" not in g.state.scenario.encounter_deck


class TestSearchForKadath:
    def test_song_of_the_magah_bird_move_out_penalty(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        doom0 = g.state.scenario.doom_on_agenda
        _resolve(ctrl, "song_of_the_magah_bird")
        assert ctrl.location_attachment_instance("test_location", "song_of_the_magah_bird")
        _move_out(g)
        assert inv.horror == 1
        assert g.state.scenario.doom_on_agenda == doom0 + 1
        assert ctrl.location_attachment_instance("test_location", "song_of_the_magah_bird") is None

    def test_song_of_the_magah_bird_activate_discard(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.actions_remaining = 3
        inv.card_data.skills.willpower = 4
        _resolve(ctrl, "song_of_the_magah_bird")
        _pass_bag(g)
        assert tde.activate_song_of_the_magah_bird(ctrl, "player") is True
        assert ctrl.location_attachment_instance("test_location", "song_of_the_magah_bird") is None

    def test_wondrous_lands_surges_without_clues(self):
        g, ctrl = _mk()
        g.state.get_location("test_location").clues = 0
        r = _resolve(ctrl, "wondrous_lands")
        assert r.get("surge") is True

    def test_wondrous_lands_investigate_penalty(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        doom0 = g.state.scenario.doom_on_agenda
        _resolve(ctrl, "wondrous_lands")  # test_location 有3线索
        assert ctrl.location_attachment_instance("test_location", "wondrous_lands")
        _clue_discovered(g)
        assert inv.horror == 1
        assert g.state.scenario.doom_on_agenda == doom0 + 1
        assert ctrl.location_attachment_instance("test_location", "wondrous_lands") is None


class TestThousandShapesOfHorror:
    def _pitch_game(self):
        g, ctrl = _mk()
        for lid in ("p2", "p3"):
            ld = make_location_data(id=lid)
            g.register_card_data(ld)
            g.add_location(lid, ld, clues=1)
        g.state.locations["test_location"].revealed = True
        g.state.locations["p2"].revealed = True
        g.state.locations["p3"].revealed = True
        g.state.scenario.vars["pitch_locations"] = ["test_location", "p2", "p3"]
        return g, ctrl

    def test_endless_descent_rotates_pitch_line(self):
        g, ctrl = self._pitch_game()
        inv = g.state.get_investigator("player")
        top = g.state.get_location("test_location")
        _resolve(ctrl, "endless_descent")
        assert inv.location_id == "p2"  # 顶端所有人下移一层
        assert top.revealed is False and top.clues == 0
        # 顶端翻回未揭示后移到底端（p2/p3 已揭示，位置不变）
        assert g.state.scenario.vars["pitch_locations"] == ["p2", "p3", "test_location"]
        assert "endless_descent" in g.state.scenario.victory_display

    def test_endless_descent_without_pitch_line_only_victory(self):
        g, ctrl = _mk()
        r = _resolve(ctrl, "endless_descent")
        assert r["message"] == "endless_descent"
        assert "endless_descent" in g.state.scenario.victory_display

    def test_indescribable_apparition_threat_and_activate(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.actions_remaining = 3
        _resolve(ctrl, "indescribable_apparition")
        assert any(g.state.cards_in_play[i].card_id == "indescribable_apparition"
                   for i in inv.threat_area)
        assert tde.activate_discard_indescribable_apparition(ctrl, "player") is True
        assert inv.actions_remaining == 1

    def test_glowing_eyes_round_end_horror_and_discard(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        _resolve(ctrl, "glowing_eyes")
        _round_ends(g)
        assert inv.horror == 1  # 威胁区仅发光的眼睛自身
        assert not any(i in g.state.cards_in_play and
                       g.state.cards_in_play[i].card_id == "glowing_eyes"
                       for i in inv.threat_area)
        assert "glowing_eyes" in g.state.scenario.encounter_discard

    def test_deceptive_memories_activate_success_discards(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.actions_remaining = 3
        _resolve(ctrl, "deceptive_memories")
        _pass_bag(g)
        assert tde.activate_deceptive_memories(ctrl, "player") is True
        assert "deceptive_memories" in g.state.scenario.encounter_discard

    def test_secrets_in_the_attic_fail_places_copy_and_round_end_discards(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.card_data.skills.willpower = 1
        _fail_bag(g)
        _resolve(ctrl, "secrets_in_the_attic")
        assert inv.horror == 1
        assert g.state.scenario.vars["secrets_in_the_attic"] == 1
        _round_ends(g)
        assert g.state.scenario.vars["secrets_in_the_attic"] == 0


class TestDarkSideOfTheMoon:
    def test_close_watch_fail_raises_alarm(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.card_data.skills.agility = 1
        _fail_bag(g)
        _resolve(ctrl, "close_watch")
        assert g.state.scenario.vars["alarm_level"]["player"] == 1

    def test_forced_into_hiding_scales_with_margin(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.card_data.skills.willpower = 1
        inv.actions_remaining = 3
        g.state.scenario.vars["alarm_level"] = {"player": 5}  # 难度5
        _fail_bag(g)  # margin 5 → 失去3行动
        _resolve(ctrl, "forced_into_hiding")
        assert inv.actions_remaining == 0

    def test_forced_into_hiding_small_margin_loses_one(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.card_data.skills.willpower = 1
        inv.actions_remaining = 3
        g.state.scenario.vars["alarm_level"] = {"player": 2}  # 难度2，margin 2
        _fail_bag(g)
        _resolve(ctrl, "forced_into_hiding")
        assert inv.actions_remaining == 2

    def test_lunar_patrol_leave_raises_alarm_and_activate_discards(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.actions_remaining = 3
        _resolve(ctrl, "lunar_patrol")
        _move_out(g)
        assert g.state.scenario.vars["alarm_level"]["player"] == 1
        _pass_bag(g)  # 敏捷3 vs 3 → 成功
        assert tde.activate_lunar_patrol(ctrl, "player") is True
        assert ctrl.location_attachment_instance("test_location", "lunar_patrol") is None

    def test_false_awakening_enters_with_doom_and_removed_on_success(self):
        for cid in ("false_awakening_a", "false_awakening_b"):
            g, ctrl = _mk()
            inv = g.state.get_investigator("player")
            inv.actions_remaining = 3
            r = _resolve(ctrl, cid)
            assert r["message"] == cid
            assert g.state.scenario.vars["false_awakening"][cid]["doom"] == 1
            _pass_bag(g)  # 意志3 vs 2+1调查员=3 → 成功
            assert tde.activate_false_awakening(ctrl, "player") is True
            assert cid in g.state.scenario.vars["removed_from_game"]
            assert "false_awakening" not in g.state.scenario.vars


class TestPointOfNoReturn:
    def test_taste_of_lifeblood_places_clues_then_damage(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.card_data.skills.willpower = 1
        inv.clues = 2
        loc = g.state.get_location("test_location")
        clues0 = loc.clues
        _fail_bag(g)  # margin 3：放2线索 + 受1伤害
        _resolve(ctrl, "taste_of_lifeblood")
        assert inv.clues == 0
        assert loc.clues == clues0 + 2
        assert inv.damage == 1

    def test_lit_by_death_fire_resource_card_and_action_loss(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.resources = 5
        inv.actions_remaining = 3
        inv.hand = ["some_card"]
        g.state.locations["test_location"].card_data.traits = ["depths"]
        _resolve(ctrl, "lit_by_death_fire")
        assert inv.resources == 4
        assert inv.hand == [] and inv.discard == ["some_card"]
        assert inv.actions_remaining == 2

    def test_lit_by_death_fire_vale_only_discards(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.actions_remaining = 3
        inv.hand = ["c1"]
        g.state.locations["test_location"].card_data.traits = ["vale"]
        _resolve(ctrl, "lit_by_death_fire")
        assert inv.discard == ["c1"]
        assert inv.actions_remaining == 3  # 非深渊不失去行动

    def test_unexpected_ambush_no_enemies(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        _resolve(ctrl, "unexpected_ambush")
        assert inv.damage == 1 and inv.horror == 1

    def test_unexpected_ambush_enemy_engages_and_attacks_on_big_fail(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.card_data.skills.intellect = 1
        inv.card_data.skills.agility = 1
        e = _add_enemy(g, "e1", "lunar_beast", ["monster"])
        e.exhausted = True
        _fail_bag(g)  # margin 4 ≥ 3 → 立即攻击
        _resolve(ctrl, "unexpected_ambush")
        assert "e1" in inv.threat_area
        assert e.exhausted is False
        assert inv.damage == 1 and inv.horror == 1  # 默认敌人1伤1恐

    def test_unexpected_ambush_small_fail_no_attack(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.card_data.skills.intellect = 3
        inv.card_data.skills.agility = 1
        _add_enemy(g, "e1", "lunar_beast", ["monster"])
        g.chaos_bag.tokens = [ChaosTokenType.MINUS_1]  # 智力3-1 vs 4 → margin 2
        _resolve(ctrl, "unexpected_ambush")
        assert "e1" in inv.threat_area
        assert inv.damage == 0 and inv.horror == 0


class TestTerrorOfTheValeAndPitch:
    def test_dhole_tunnel_in_play_moves_and_attacks(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        _add_enemy(g, "dh1", "slithering_dhole", ["monster", "dhole", "elite"])
        _resolve(ctrl, "dhole_tunnel")
        assert "dh1" in inv.threat_area
        assert inv.damage == 1 and inv.horror == 1

    def test_dhole_tunnel_attach_two_away_and_spawn_from_victory(self):
        g, ctrl = _mk()
        # 地点链 a(test_location) - b - c；已有隧道在 a → 只能叠加到 c
        for lid, conns in (("b", ["test_location", "c"]), ("c", ["b"])):
            ld = make_location_data(id=lid, connections=conns)
            g.register_card_data(ld)
            g.add_location(lid, ld, clues=1)
        g.state.locations["test_location"].card_data.connections = ["b"]
        ctrl.attach_card_to_location("dhole_tunnel", "test_location")
        _resolve(ctrl, "dhole_tunnel")
        assert ctrl.location_attachment_instance("c", "dhole_tunnel")

    def test_dhole_tunnel_spans_from_victory_display(self):
        g, ctrl = _mk()
        g.register_card_data(make_enemy_data(id="slithering_dhole",
                                             keywords=["monster", "dhole", "elite"]))
        g.state.scenario.victory_display.append("slithering_dhole")
        _resolve(ctrl, "dhole_tunnel")  # 无其他隧道 → 叠加到当前地点
        assert ctrl.location_attachment_instance("test_location", "dhole_tunnel")
        assert "slithering_dhole" not in g.state.scenario.victory_display
        spawned = [i for i, inst in g.state.cards_in_play.items()
                   if inst.card_id == "slithering_dhole"]
        assert spawned
        inst = g.state.get_card_instance(spawned[0])
        assert inst.exhausted is True
        assert spawned[0] in g.state.get_location("test_location").enemies

    def test_shadow_of_atlach_nacha_scales_with_reference_damage(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.card_data.skills.willpower = 3
        g.state.scenario.vars["scenario_reference_damage"] = 1  # 难度3
        g.chaos_bag.tokens = [ChaosTokenType.MINUS_1]  # 3-1 vs 3 → 失败
        _resolve(ctrl, "shadow_of_atlach_nacha")
        assert inv.damage == 1 and inv.horror == 1


class TestWhereTheGodsDwell:
    def test_whispering_chaos_enters_hand(self):
        for cid in ("whispering_chaos_a", "whispering_chaos_b",
                    "whispering_chaos_c", "whispering_chaos_d"):
            g, ctrl = _mk()
            inv = g.state.get_investigator("player")
            r = _resolve(ctrl, cid)
            assert r["message"] == cid
            assert cid in inv.hand
            assert g.state.scenario.vars["whispering_chaos"]["player"] == cid

    def test_myriad_forms_surges_without_nyarlathotep(self):
        g, ctrl = _mk()
        r = _resolve(ctrl, "myriad_forms")
        assert r.get("surge") is True

    def test_myriad_forms_hand_copy_attacks_and_shuffles_into_deck(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        g.register_card_data(make_enemy_data(id="nyarlathotep_a",
                                             keywords=["ancient one", "elite"]))
        inv.hand.append("nyarlathotep_a")
        r = _resolve(ctrl, "myriad_forms")
        assert r["message"] == "myriad_forms"
        assert inv.horror == 1  # nyarlathotep_a 无伤害、1恐惧
        assert "nyarlathotep_a" not in inv.hand
        assert "nyarlathotep_a" in g.state.scenario.encounter_deck

    def test_myriad_forms_in_play_moves_and_attacks(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        _add_enemy(g, "ny1", "nyarlathotep_b", ["ancient one", "elite"])
        r = _resolve(ctrl, "myriad_forms")
        assert r.get("surge") is None
        assert "ny1" in inv.threat_area
        assert inv.damage == 1  # nyarlathotep_b 1伤害、无恐惧

    def test_restless_journey_enters_hand(self):
        for cid in ("restless_journey_a", "restless_journey_b", "restless_journey_c"):
            g, ctrl = _mk()
            inv = g.state.get_investigator("player")
            _resolve(ctrl, cid)
            assert cid in inv.hand
            assert g.state.scenario.vars["restless_journey"]["player"] == cid

    def test_restless_journey_activate_fail_places_doom(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.card_data.skills.intellect = 1
        doom0 = g.state.scenario.doom_on_agenda
        _resolve(ctrl, "restless_journey_a")
        _fail_bag(g)
        assert tde.activate_restless_journey(ctrl, "player") is True
        assert "restless_journey_a" in inv.discard
        assert g.state.scenario.doom_on_agenda == doom0 + 1

    def test_abandoned_by_the_gods_discards_least_punishing_numbers(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.card_data.skills.willpower = 1
        _register_asset(g, "cost0", cost=0)
        _register_asset(g, "cost2", cost=2)
        g.register_card_data(make_event_data(id="cost1", cost=1))
        inv.hand = ["cost0", "cost1", "cost2"]
        _fail_bag(g)  # margin 3 → 选3个数字：3,4（无匹配）+0（平局取小）
        _resolve(ctrl, "abandoned_by_the_gods")
        assert inv.discard == ["cost0"]
        assert sorted(inv.hand) == ["cost1", "cost2"]


class TestWeaverOfTheCosmos:
    def test_spinner_in_darkness_no_ancient_one_is_discarded(self):
        g, ctrl = _mk()
        r = _resolve(ctrl, "the_spinner_in_darkness")
        assert r["message"] == "the_spinner_in_darkness"
        assert "spinner_in_darkness" not in g.state.scenario.vars

    def test_spinner_in_darkness_attaches_and_activate_discards(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.card_data.skills.willpower = 6
        inv.actions_remaining = 3
        _add_enemy(g, "ao1", "atlach_nacha", ["ancient one", "elite"])
        _resolve(ctrl, "the_spinner_in_darkness")
        rec = g.state.scenario.vars["spinner_in_darkness"]
        assert "ao1" in rec
        assert g.state.cards_in_play[rec["ao1"]].attached_to == "ao1"
        _pass_bag(g)  # 意志6 vs 5 → 成功
        assert tde.activate_spinner_in_darkness(ctrl, "player") is True
        assert "spinner_in_darkness" not in g.state.scenario.vars
        assert "the_spinner_in_darkness" in g.state.scenario.encounter_discard

    def test_caught_in_a_web_threat_and_activate(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.actions_remaining = 3
        _resolve(ctrl, "caught_in_a_web")
        assert any(g.state.cards_in_play[i].card_id == "caught_in_a_web"
                   for i in inv.threat_area)
        assert g.state.scenario.vars["caught_in_a_web"]["player"] is True
        _pass_bag(g)  # 战斗3 vs 3 → 成功
        assert tde.activate_caught_in_a_web(ctrl, "player") is True
        assert "caught_in_a_web" in g.state.scenario.encounter_discard

    def test_endless_weaving_engaged_spider_attacks(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        _add_enemy(g, "sp1", "swarm_spider", ["spider"], engaged=True)
        _resolve(ctrl, "endless_weaving")
        assert inv.damage == 1 and inv.horror == 1

    def test_endless_weaving_unengaged_spider_places_doom(self):
        g, ctrl = _mk()
        loc = g.state.get_location("test_location")
        doom0 = loc.doom
        _add_enemy(g, "sp1", "swarm_spider", ["spider"])
        _resolve(ctrl, "endless_weaving")
        assert loc.doom == doom0 + 1

    def test_endless_weaving_pulls_spider_from_deck(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        g.register_card_data(make_enemy_data(id="web-spinner", keywords=["spider"]))
        _register_treachery(g, "filler")
        g.state.scenario.encounter_deck = ["filler", "web-spinner"]
        _resolve(ctrl, "endless_weaving")
        spawned = [i for i, inst in g.state.cards_in_play.items()
                   if inst.card_id == "web-spinner"]
        assert spawned and spawned[0] in inv.threat_area


class TestCoverage:
    def test_all_tde_treacheries_handled(self):
        """the_dream_eaters.json 中全部47张诡计都由本模块处理（无核心重印需跳过）。"""
        import json
        from pathlib import Path
        data = json.loads((Path(__file__).resolve().parents[2]
                           / "data/encounter_cards/the_dream_eaters.json").read_text())
        ids = [c["id"] for c in data["cards"] if c.get("type") == "treachery"]
        assert len(ids) == 47
        for cid in ids:
            g, ctrl = _mk()
            g.state.scenario.vars.pop("pending_choice", None)
            r = _resolve(ctrl, cid)
            assert r is not None, cid
