"""Tests for The Forgotten Age encounter treachery effects."""

from __future__ import annotations

from backend.engine.event_bus import EventContext
from backend.models.enums import CardType, ChaosTokenType, GameEvent
from backend.models.state import CardData, CardInstance
from backend.scenarios import encounters_the_forgotten_age as tfa
from backend.tests.conftest import make_asset_data, make_enemy_data, make_location_data
from backend.tests.test_scenario_tokens import _add_enemy, _make_game


def _mk(scenario_id="wilds"):
    return _make_game(scenario_id)


def _fail_bag(g):
    """Force the next skill test to fail (margin = difficulty)."""
    g.chaos_bag.tokens = [ChaosTokenType.AUTO_FAIL]


def _pass_bag(g):
    g.chaos_bag.tokens = [ChaosTokenType.ZERO]


def _resolve(ctrl, card_id, choice=None):
    return tfa.resolve_treachery(ctrl, card_id, investigator_id="player", choice=choice)


def _turn_end(g, inv_id="player"):
    g.event_bus.emit(EventContext(
        game_state=g.state, event=GameEvent.INVESTIGATOR_TURN_ENDS,
        investigator_id=inv_id))


def _round_end(g):
    g.event_bus.emit(EventContext(game_state=g.state, event=GameEvent.ROUND_ENDS))


def _register_asset(g, card_id, cost=0, traits=None, unique=False):
    cd = make_asset_data(id=card_id, cost=cost, traits=traits or [])
    cd.unique = unique
    g.register_card_data(cd)
    return cd


def _add_asset(g, inv, instance_id, card_id, damage=0, horror=0):
    inst = CardInstance(instance_id=instance_id, card_id=card_id,
                        owner_id="player", controller_id="player")
    inst.damage = damage
    inst.horror = horror
    g.state.cards_in_play[instance_id] = inst
    inv.play_area.append(instance_id)
    return inst


def _add_location(g, location_id, traits=None, clues=0):
    cd = make_location_data(id=location_id)
    cd.traits = traits or []
    g.register_card_data(cd)
    return g.add_location(location_id, cd, clues=clues)


def _threat_ids(g, inv, card_id):
    return [i for i in inv.threat_area
            if i in g.state.cards_in_play
            and g.state.cards_in_play[i].card_id == card_id]


class TestRainforest:
    def test_overgrowth_attach_and_activate_discard(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        r = _resolve(ctrl, "overgrowth")
        assert r["message"] == "overgrowth"
        assert ctrl.location_attachment_instance("test_location", "overgrowth")
        assert g.state.scenario.vars["overgrowth"]["test_location"] is True

        inv.card_data.skills.combat = 10
        _pass_bag(g)
        assert tfa.activate_overgrowth(ctrl, "player") is True
        assert inv.actions_remaining == 2
        assert ctrl.location_attachment_instance("test_location", "overgrowth") is None
        assert "test_location" not in g.state.scenario.vars["overgrowth"]

    def test_overgrowth_second_copy_discarded(self):
        g, ctrl = _mk()
        _resolve(ctrl, "overgrowth")
        r = _resolve(ctrl, "overgrowth")
        assert r.get("surge") is None
        assert len(ctrl.location_attachment_ids("test_location")) == 1

    def test_voice_of_the_jungle_turn_end_horror_and_activate(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        _resolve(ctrl, "voice_of_the_jungle")
        assert _threat_ids(g, inv, "voice_of_the_jungle")
        _turn_end(g)  # 未探索 → 1恐惧
        assert inv.horror == 1

        _pass_bag(g)  # 意志3 vs 3 → 成功
        assert tfa.activate_voice_of_the_jungle(ctrl, "player") is True
        assert not _threat_ids(g, inv, "voice_of_the_jungle")
        _turn_end(g)
        assert inv.horror == 1  # 弃掉后不再触发

    def test_voice_of_the_jungle_explored_turn_no_horror(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        _resolve(ctrl, "voice_of_the_jungle")
        g.state.scenario.vars["explored_this_turn"] = ["player"]
        _turn_end(g)
        assert inv.horror == 0


class TestSerpentsAndExpedition:
    def test_snake_bite_fail_deals_five_to_ally(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        _register_asset(g, "ally_a", traits=["ally"])
        ally = _add_asset(g, inv, "al1", "ally_a")
        _fail_bag(g)
        _resolve(ctrl, "snake_bite")
        assert ally.damage == 5
        assert inv.damage == 0
        assert not _threat_ids(g, inv, "poisoned")

    def test_snake_bite_fail_no_ally_direct_damage_and_poisoned(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        _fail_bag(g)
        _resolve(ctrl, "snake_bite")
        assert inv.damage == 1
        assert _threat_ids(g, inv, "poisoned")

    def test_lost_in_the_wilds_fail_horror_and_threat_then_turn_end_discard(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        _fail_bag(g)  # 难度3 → 3恐惧
        _resolve(ctrl, "lost_in_the_wilds")
        assert inv.horror == 3
        assert _threat_ids(g, inv, "lost_in_the_wilds")
        assert g.state.scenario.vars["lost_in_the_wilds"]["player"] is True
        _turn_end(g)
        assert not _threat_ids(g, inv, "lost_in_the_wilds")
        assert "player" not in g.state.scenario.vars["lost_in_the_wilds"]

    def test_low_on_supplies_pending_then_take_damage(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        r = _resolve(ctrl, "low_on_supplies")
        assert r["pending"] is True
        pc = g.state.scenario.vars["pending_choice"]
        assert pc["investigator_id"] == "player"
        g.state.scenario.vars.pop("pending_choice")
        r = _resolve(ctrl, "low_on_supplies", choice="take_damage")
        assert r["pending"] is False
        assert inv.damage == 1

    def test_low_on_supplies_lose_resources_and_discard_asset(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.resources = 5
        _resolve(ctrl, "low_on_supplies", choice="lose_resources")
        assert inv.resources == 3

        g2, ctrl2 = _mk()
        inv2 = g2.state.get_investigator("player")
        _register_asset(g2, "asset_a", cost=1)
        _add_asset(g2, inv2, "a1", "asset_a")
        _resolve(ctrl2, "low_on_supplies", choice="discard_asset")
        assert "asset_a" in inv2.discard
        assert "a1" not in inv2.play_area


class TestAgentsAndGuardians:
    def test_curse_of_yig_health_penalty_and_activate(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        health0 = inv.health
        _resolve(ctrl, "curse_of_yig")
        assert _threat_ids(g, inv, "curse_of_yig")
        assert inv.health == health0 - 1

        _pass_bag(g)  # 意志3 vs 2 → 成功
        assert tfa.activate_curse_of_yig(ctrl, "player") is True
        assert not _threat_ids(g, inv, "curse_of_yig")
        assert inv.health == health0

    def test_curse_of_yig_vengeance_raises_difficulty(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        _resolve(ctrl, "curse_of_yig")
        g.state.scenario.vars["vengeance"] = 2  # 难度 2+2=4 > 意志3
        _pass_bag(g)
        assert tfa.activate_curse_of_yig(ctrl, "player") is True
        assert _threat_ids(g, inv, "curse_of_yig")  # 失败，仍在威胁区

    def test_arrows_from_the_trees_damage_scales_with_allies(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        _register_asset(g, "ally_a", traits=["ally"])
        _register_asset(g, "ally_b", traits=["ally"])
        _add_asset(g, inv, "al1", "ally_a")
        _add_asset(g, inv, "al2", "ally_b")
        _resolve(ctrl, "arrows_from_the_trees")
        assert inv.damage == 3

    def test_final_mistake_difficulty_scales_with_location_doom(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        loc = g.state.get_location("test_location")
        loc.doom = 2  # 难度 2+2=4
        _fail_bag(g)
        _resolve(ctrl, "final_mistake")
        assert inv.damage == 2

    def test_entombed_activate_fail_reduces_difficulty_until_round_end(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        _resolve(ctrl, "entombed")
        assert _threat_ids(g, inv, "entombed")
        rec = g.state.scenario.vars["entombed"]["player"]

        _fail_bag(g)  # 敏捷3 vs 4 → 失败
        assert tfa.activate_entombed(ctrl, "player") is True
        assert rec["reduction"] == 1
        _round_end(g)
        assert rec["reduction"] == 0

        inv.card_data.skills.agility = 10
        _pass_bag(g)
        assert tfa.activate_entombed(ctrl, "player") is True
        assert not _threat_ids(g, inv, "entombed")
        assert "player" not in g.state.scenario.vars["entombed"]


class TestFluxAndRuins:
    def test_a_tear_in_time_loses_actions_first_then_horror(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.actions_remaining = 3
        _fail_bag(g)  # 难度3 → 失3行动
        _resolve(ctrl, "a_tear_in_time")
        assert inv.actions_remaining == 0
        assert inv.horror == 0

        g2, ctrl2 = _mk()
        inv2 = g2.state.get_investigator("player")
        inv2.actions_remaining = 1
        _fail_bag(g2)  # 失1行动 + 2恐惧
        _resolve(ctrl2, "a_tear_in_time")
        assert inv2.actions_remaining == 0
        assert inv2.horror == 2

    def test_lost_in_time_shuffles_asset_and_moves_counters(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        _register_asset(g, "asset_a")
        _add_asset(g, inv, "a1", "asset_a", damage=2, horror=1)
        inv.deck = ["x", "y"]
        _resolve(ctrl, "lost_in_time")
        assert "asset_a" in inv.deck
        assert "a1" not in inv.play_area
        assert inv.damage == 2 and inv.horror == 1

    def test_lost_in_time_no_asset_discards_three_from_hand(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.hand = ["a", "b", "c", "d"]
        _resolve(ctrl, "lost_in_time")
        assert inv.hand == ["d"]
        assert inv.discard == ["a", "b", "c"]

    def test_ill_omen_doom_and_horror_at_own_location(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        loc = g.state.get_location("test_location")
        doom0 = loc.doom
        _resolve(ctrl, "ill_omen")
        assert loc.doom == doom0 + 1
        assert inv.horror == 1

    def test_ancestral_fear_pending_then_victory_display_surge(self):
        g, ctrl = _mk()
        r = _resolve(ctrl, "ancestral_fear")
        assert r["pending"] is True
        assert g.state.scenario.vars["pending_choice"]["investigator_id"] == "player"
        g.state.scenario.vars.pop("pending_choice")
        r = _resolve(ctrl, "ancestral_fear", choice="victory_display")
        assert r.get("surge") is True
        assert "ancestral_fear" in g.state.scenario.victory_display

    def test_ancestral_fear_place_doom_branch(self):
        g, ctrl = _mk()
        loc = g.state.get_location("test_location")
        doom0 = loc.doom
        r = _resolve(ctrl, "ancestral_fear", choice="place_doom")
        assert r.get("surge") is True
        assert loc.doom == doom0 + 1
        assert "ancestral_fear" not in g.state.scenario.victory_display

    def test_deep_dark_discards_one_copy_per_round(self):
        g, ctrl = _mk()
        _resolve(ctrl, "deep_dark")
        _resolve(ctrl, "deep_dark")
        assert g.state.scenario.vars["deep_dark"] == 2
        _round_end(g)
        assert g.state.scenario.vars["deep_dark"] == 1
        _round_end(g)
        assert "deep_dark" not in g.state.scenario.vars


class TestPnakoticAndVenom:
    def test_shadowed_no_cultist_horror_and_surge(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        r = _resolve(ctrl, "shadowed")
        assert r.get("surge") is True
        assert inv.horror == 1

    def test_shadowed_dooms_nearest_cultist_and_tests_fight(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        e = _add_enemy(g, "e1", "brotherhood_cultist", ["cultist"])  # 战斗3
        _fail_bag(g)  # 意志 vs 3 → 失败
        _resolve(ctrl, "shadowed")
        assert e.doom == 1
        assert inv.horror == 2

    def test_words_of_power_threat_and_activate(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        _resolve(ctrl, "words_of_power")
        assert _threat_ids(g, inv, "words_of_power")
        assert tfa.activate_words_of_power(ctrl, "player") is True
        assert inv.actions_remaining == 1
        assert not _threat_ids(g, inv, "words_of_power")

    def test_snakescourge_no_surge_unless_poisoned_and_round_end_discard(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        r = _resolve(ctrl, "snakescourge")
        assert r.get("surge") is None
        assert _threat_ids(g, inv, "snakescourge")
        _round_end(g)
        assert not _threat_ids(g, inv, "snakescourge")
        assert "player" not in g.state.scenario.vars["snakescourge"]

    def test_snakescourge_surges_when_poisoned(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        _resolve(ctrl, "poisoned")
        r = _resolve(ctrl, "snakescourge")
        assert r.get("surge") is True

    def test_serpents_call_pending_then_poisoned(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        r = _resolve(ctrl, "serpents_call")
        assert r["pending"] is True
        g.state.scenario.vars.pop("pending_choice")
        _resolve(ctrl, "serpents_call", choice="poisoned")
        assert _threat_ids(g, inv, "poisoned")

    def test_serpents_call_draw_two_encounter_cards(self):
        g, ctrl = _mk()
        _pass_bag(g)  # rotting_remains 意志3 vs 3 → 成功
        g.state.scenario.encounter_deck = ["ancient_evils", "rotting_remains"]
        doom0 = g.state.scenario.doom_on_agenda
        _resolve(ctrl, "serpents_call", choice="draw_encounter")
        assert g.state.scenario.doom_on_agenda == doom0 + 1  # ancient_evils
        assert g.state.scenario.encounter_deck == []
        assert "ancient_evils" in g.state.scenario.encounter_discard
        assert "rotting_remains" in g.state.scenario.encounter_discard


class TestPoisonAndThreadsOfFate:
    def test_creeping_poison_damages_poisoned_and_surges(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        r = _resolve(ctrl, "creeping_poison")
        assert r.get("surge") is True
        assert inv.damage == 0  # 未中毒不伤

        _resolve(ctrl, "poisoned")
        r = _resolve(ctrl, "creeping_poison")
        assert inv.damage == 1

    def test_poisoned_enters_threat_area_limit_one(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        _resolve(ctrl, "poisoned")
        _resolve(ctrl, "poisoned")
        assert len(_threat_ids(g, inv, "poisoned")) == 1

    def test_secret_must_be_kept_scales_with_completed_acts(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        g.state.scenario.current_act_index = 1  # 已完成1个场景 → 难度4，2伤2恐
        _fail_bag(g)
        _resolve(ctrl, "the_secret_must_be_kept")
        assert inv.damage == 2 and inv.horror == 2

    def test_nobodys_home_attach_and_discard_when_clues_gone(self):
        g, ctrl = _mk()
        loc = g.state.get_location("test_location")
        assert loc.clues > 0
        r = _resolve(ctrl, "nobodys_home")
        assert r.get("surge") is None
        assert ctrl.location_attachment_instance("test_location", "nobodys_home")

        loc.clues = 0
        g.event_bus.emit(EventContext(
            game_state=g.state, event=GameEvent.CLUE_DISCOVERED,
            investigator_id="player", location_id="test_location"))
        assert ctrl.location_attachment_instance("test_location", "nobodys_home") is None

    def test_nobodys_home_surges_when_no_clues(self):
        g, ctrl = _mk()
        loc = g.state.get_location("test_location")
        loc.clues = 0
        r = _resolve(ctrl, "nobodys_home")
        assert r.get("surge") is True
        assert ctrl.location_attachment_instance("test_location", "nobodys_home") is None

    def test_conspiracy_of_blood_parley_success_and_failure(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        _resolve(ctrl, "conspiracy_of_blood")
        assert g.state.scenario.vars["conspiracy_of_blood"] == 1
        e = _add_enemy(g, "e1", "brotherhood_cultist", ["cultist"])

        _fail_bag(g)  # 意志3 vs 4 → 失败：异教徒+1毁灭
        assert tfa.activate_conspiracy_of_blood(ctrl, "player", "e1") is True
        assert e.doom == 1
        assert g.state.scenario.vars["conspiracy_of_blood"] == 1

        inv.card_data.skills.willpower = 5
        _pass_bag(g)
        assert tfa.activate_conspiracy_of_blood(ctrl, "player", "e1") is True
        assert "conspiracy_of_blood" not in g.state.scenario.vars


class TestBoundaryBeyondAndHeartOfTheElders:
    def test_window_to_another_time_pending_then_place_doom(self):
        g, ctrl = _mk()
        r = _resolve(ctrl, "window_to_another_time")
        assert r["pending"] is True
        g.state.scenario.vars.pop("pending_choice")
        doom0 = g.state.scenario.doom_on_agenda
        _resolve(ctrl, "window_to_another_time", choice="place_doom")
        assert g.state.scenario.doom_on_agenda == doom0 + 1

    def test_window_to_another_time_shuffle_ancient_location(self):
        g, ctrl = _mk()
        _add_location(g, "ancient_loc", traits=["ancient"])
        _resolve(ctrl, "window_to_another_time", choice="shuffle_location")
        assert "ancient_loc" not in g.state.locations
        assert g.state.scenario.vars["exploration_deck"] == ["ancient_loc"]
        assert g.state.scenario.vars["returned_to_exploration"] == ["ancient_loc"]

    def test_timeline_destabilization_scales_with_ancient_locations(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        _add_location(g, "ancient_loc", traits=["ancient"])  # 难度 1+1=2
        _fail_bag(g)
        _resolve(ctrl, "timeline_destabilization")
        assert inv.damage == 1 and inv.horror == 1
        assert g.state.scenario.vars["exploration_deck"] == ["timeline_destabilization"]

    def test_pitfall_pending_then_test_branch(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        r = _resolve(ctrl, "pitfall")
        assert r["pending"] is True
        g.state.scenario.vars.pop("pending_choice")
        _fail_bag(g)  # 难度3 → 3伤害
        _resolve(ctrl, "pitfall", choice="test_agility")
        assert inv.damage == 3

    def test_pitfall_shuffle_branch(self):
        g, ctrl = _mk()
        _resolve(ctrl, "pitfall", choice="shuffle_back")
        assert g.state.scenario.vars["exploration_deck"] == ["pitfall"]

    def test_poisonous_spores_round_end_poisons_investigator(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        _resolve(ctrl, "poisonous_spores")
        assert ctrl.location_attachment_instance("test_location", "poisonous_spores")
        _round_end(g)
        assert _threat_ids(g, inv, "poisoned")
        assert ctrl.location_attachment_instance("test_location", "poisonous_spores") is None

    def test_poisonous_spores_round_end_horror_when_poisoned(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        _resolve(ctrl, "poisoned")
        _resolve(ctrl, "poisonous_spores")
        _round_end(g)
        assert inv.horror == 2
        assert len(_threat_ids(g, inv, "poisoned")) == 1

    def test_ants_discards_hand_then_play_area(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        _register_asset(g, "asset_a")
        _add_asset(g, inv, "a1", "asset_a")
        inv.hand = ["x", "y"]
        _fail_bag(g)  # 难度4 → 弃4张：手牌2 + 场上1（第4点无牌可弃）
        _resolve(ctrl, "ants")
        assert inv.hand == []
        assert "a1" not in inv.play_area
        assert "asset_a" in inv.discard


class TestKnyanAndCityOfArchives:
    def test_no_turning_back_attach_and_pickaxe_discard(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        _resolve(ctrl, "no_turning_back")
        assert ctrl.location_attachment_instance("test_location", "no_turning_back")
        g.state.scenario.vars["supplies"] = {"player": ["pickaxe"]}
        assert tfa.activate_no_turning_back(ctrl, "player") is True
        assert ctrl.location_attachment_instance("test_location", "no_turning_back") is None
        assert inv.actions_remaining == 2

    def test_no_turning_back_combat_test_discard(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.card_data.skills.combat = 10
        _resolve(ctrl, "no_turning_back")
        _pass_bag(g)
        assert tfa.activate_no_turning_back(ctrl, "player") is True
        assert ctrl.location_attachment_instance("test_location", "no_turning_back") is None

    def test_yithian_presence_activate_discards_two_cards(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        _resolve(ctrl, "yithian_presence")
        assert _threat_ids(g, inv, "yithian_presence")
        inv.hand = ["a", "b", "c"]
        assert tfa.activate_yithian_presence(ctrl, "player") is True
        assert inv.hand == ["c"]
        assert inv.actions_remaining == 2
        assert not _threat_ids(g, inv, "yithian_presence")

    def test_cruel_interrogations_surge_when_interviewed(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        g.state.scenario.vars["interviewed_subjects"] = 1
        r = _resolve(ctrl, "cruel_interrogations")
        assert r.get("surge") is True
        assert inv.horror == 1

    def test_cruel_interrogations_no_surge_and_activate(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        r = _resolve(ctrl, "cruel_interrogations")
        assert r.get("surge") is None
        _pass_bag(g)  # 意志3 vs 2 → 成功
        assert tfa.activate_cruel_interrogations(ctrl, "player") is True
        assert not _threat_ids(g, inv, "cruel_interrogations")

    def test_lost_humanity_removes_deck_top(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.deck = [f"c{i}" for i in range(15)]
        _fail_bag(g)  # 难度5 → 移除5张
        _resolve(ctrl, "lost_humanity")
        assert len(inv.deck) == 10
        assert len(g.state.scenario.vars["removed_from_game"]) == 5
        assert "player" not in g.state.scenario.vars.get("insane_investigators", [])

    def test_lost_humanity_driven_insane_below_ten_cards(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.deck = [f"c{i}" for i in range(5)]
        _fail_bag(g)
        _resolve(ctrl, "lost_humanity")
        assert "player" in g.state.scenario.vars["insane_investigators"]
        assert inv.is_defeated

    def test_captive_mind_keeps_modified_skill_cards_on_success(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.hand = ["a", "b", "c", "d", "e"]
        _pass_bag(g)  # 意志3 → 保留3张
        _resolve(ctrl, "captive_mind")
        assert len(inv.hand) == 3
        assert len(inv.discard) == 2

    def test_captive_mind_auto_fail_discards_all(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.hand = ["a", "b", "c"]
        _fail_bag(g)  # 修正0 → 全弃
        _resolve(ctrl, "captive_mind")
        assert inv.hand == []
        assert len(inv.discard) == 3

    def test_out_of_body_experience_replaces_hand_and_shuffles_self(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.hand = ["a", "b", "c"]
        inv.deck = ["d1", "d2", "d3", "d4", "d5"]
        _resolve(ctrl, "out_of_body_experience")
        assert len(inv.hand) == 3
        assert "out_of_body_experience" in inv.deck
        assert len(inv.deck) == 6  # 5 + 3洗回 - 3抽取 + 1自身


class TestDepthsOfYoth:
    def test_children_of_valusia_round_end_countdown(self):
        g, ctrl = _mk()
        _resolve(ctrl, "children_of_valusia")
        _resolve(ctrl, "children_of_valusia")
        assert g.state.scenario.vars["children_of_valusia"] == 2
        _round_end(g)
        assert g.state.scenario.vars["children_of_valusia"] == 1
        _round_end(g)
        assert "children_of_valusia" not in g.state.scenario.vars

    def test_lightless_shadow_scales_with_depth(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        g.state.scenario.vars["depth"] = 2  # 难度3
        _fail_bag(g)
        _resolve(ctrl, "lightless_shadow")
        assert inv.damage == 2

    def test_bathophobia_scales_with_depth(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        g.state.scenario.vars["depth"] = 3  # 难度4
        _fail_bag(g)
        _resolve(ctrl, "bathophobia")
        assert inv.horror == 2

    def test_serpents_ire_surges_without_pursuit(self):
        g, ctrl = _mk()
        r = _resolve(ctrl, "serpents_ire")
        assert r.get("surge") is True

    def test_serpents_ire_spawns_highest_fight_and_attacks_on_fail(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        g.register_card_data(make_enemy_data(id="pit_viper", fight=3, damage=2, horror=1,
                                             keywords=["serpent"]))
        g.register_card_data(make_enemy_data(id="boa_constrictor", fight=4, damage=1,
                                             horror=0, keywords=["serpent"]))
        g.state.scenario.vars["in_pursuit"] = ["pit_viper", "boa_constrictor"]
        _fail_bag(g)  # 敏捷3 vs 战斗4 → 失败
        _resolve(ctrl, "serpents_ire")
        spawned = _threat_ids(g, inv, "boa_constrictor")
        assert spawned
        assert g.state.scenario.vars["in_pursuit"] == ["pit_viper"]
        assert inv.damage == 1 and inv.horror == 0  # 立即攻击


class TestShatteredAeons:
    def test_shattered_ages_adds_clues_except_nexus(self):
        g, ctrl = _mk()
        loc = g.state.get_location("test_location")
        clues0 = loc.clues
        loc2 = _add_location(g, "loc2", clues=1)
        nexus = _add_location(g, "nexus_loc", clues=2)
        g.state.scenario.vars["nexus_location_id"] = "nexus_loc"
        _fail_bag(g)
        _resolve(ctrl, "shattered_ages")
        assert loc.clues == clues0 + 1
        assert loc2.clues == 2
        assert nexus.clues == 2

    def test_between_worlds_location_and_round_end_damage(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        g.state.scenario.vars["nexus_location_id"] = "test_location"
        _resolve(ctrl, "between_worlds")
        loc = g.state.get_location("between_worlds")
        assert loc is not None and loc.clues == 1 and loc.shroud == 3
        assert inv.location_id == "between_worlds"
        _round_end(g)
        assert inv.damage == 1 and inv.horror == 1

    def test_between_worlds_discards_when_empty_and_moves_enemies(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        g.state.scenario.vars["nexus_location_id"] = "test_location"
        _resolve(ctrl, "between_worlds")
        inv.location_id = "test_location"  # 离开
        g.state.locations["between_worlds"].enemies.append("e1")
        _round_end(g)
        assert "between_worlds" not in g.state.locations
        assert "e1" in g.state.locations["test_location"].enemies

    def test_wracked_by_time_damage_and_shuffle_damaged_asset(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        _register_asset(g, "asset_a")
        _add_asset(g, inv, "a1", "asset_a", damage=1)
        inv.deck = ["x"]
        _fail_bag(g)
        _resolve(ctrl, "wracked_by_time")
        assert inv.damage == 2
        assert "asset_a" in inv.deck
        assert "a1" not in inv.play_area

    def test_creeping_darkness_attach_doom_and_activate_with_torches(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        g.state.scenario.vars["nexus_location_id"] = "test_location"
        _resolve(ctrl, "creeping_darkness")
        iid = ctrl.location_attachment_instance("test_location", "creeping_darkness")
        assert iid is not None
        assert g.state.cards_in_play[iid].doom == 1

        g.state.scenario.vars["supplies"] = {"player": ["torches"]}
        assert tfa.activate_creeping_darkness(ctrl, "player") is True
        assert inv.actions_remaining == 1
        assert ctrl.location_attachment_instance("test_location", "creeping_darkness") is None
        assert "creeping_darkness" not in g.state.scenario.vars

    def test_creeping_darkness_willpower_test_discard(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.card_data.skills.willpower = 10
        _resolve(ctrl, "creeping_darkness")  # 无 nexus → 叠加到自己地点
        _pass_bag(g)
        assert tfa.activate_creeping_darkness(ctrl, "player") is True
        assert ctrl.location_with_attachment("creeping_darkness") is None


class TestCoverage:
    def test_all_tfa_treacheries_handled(self):
        """the_forgotten_age.json 中全部42张诡计都由本模块处理（无核心重印）。"""
        import json
        from pathlib import Path
        data = json.loads((Path(__file__).resolve().parents[2]
                           / "data/encounter_cards/the_forgotten_age.json").read_text())
        ids = [c["id"] for c in data["cards"] if c.get("type") == "treachery"]
        assert len(ids) == 42
        for cid in ids:
            g, ctrl = _mk()
            g.state.scenario.vars.pop("pending_choice", None)
            r = _resolve(ctrl, cid)
            assert r is not None, cid
