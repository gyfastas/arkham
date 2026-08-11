"""Tests for The Innsmouth Conspiracy encounter treachery effects."""

from __future__ import annotations

from backend.engine.event_bus import EventContext
from backend.models.enums import ChaosTokenType, GameEvent, Skill
from backend.models.state import CardInstance
from backend.scenarios import encounters_innsmouth_conspiracy as tic
from backend.tests.conftest import (
    make_asset_data,
    make_enemy_data,
    make_investigator_data,
    make_location_data,
)
from backend.tests.test_scenario_tokens import _make_game


def _mk():
    return _make_game("in_too_deep")


def _fail_bag(g):
    """Force the next skill test(s) to fail (margin = difficulty)."""
    g.chaos_bag.tokens = [ChaosTokenType.AUTO_FAIL]


def _pass_bag(g):
    g.chaos_bag.tokens = [ChaosTokenType.ZERO]


def _resolve(ctrl, card_id, choice=None, inv_id="player"):
    return tic.resolve_treachery(ctrl, card_id, investigator_id=inv_id, choice=choice)


def _add_location(g, loc_id, connections=None, traits=None):
    data = make_location_data(id=loc_id, connections=list(connections or []))
    data.traits = list(traits or [])
    g.register_card_data(data)
    g.add_location(loc_id, data, clues=0)
    return data


def _connect(g, a, b):
    g.state.locations[a].card_data.connections = [b]
    g.state.locations[b].card_data.connections = [a]


def _add_enemy(g, instance_id, card_id, keywords=None, traits=None,
               location="test_location", engaged=False, fight=3, damage=1, horror=1):
    cd = make_enemy_data(id=card_id, fight=fight, damage=damage, horror=horror,
                         keywords=list(keywords or []))
    cd.traits = list(traits or [])
    g.register_card_data(cd)
    enemy = CardInstance(instance_id=instance_id, card_id=card_id,
                         owner_id="scenario", controller_id="scenario")
    g.state.cards_in_play[instance_id] = enemy
    if engaged:
        g.state.get_investigator("player").threat_area.append(instance_id)
    else:
        g.state.locations[location].enemies.append(instance_id)
    return enemy


def _add_asset(g, inv, instance_id, card_id, cost=2, traits=None):
    cd = make_asset_data(id=card_id, cost=cost)
    cd.traits = list(traits or [])
    g.register_card_data(cd)
    inst = CardInstance(instance_id=instance_id, card_id=card_id,
                        owner_id=inv.investigator_id, controller_id=inv.investigator_id)
    g.state.cards_in_play[instance_id] = inst
    inv.play_area.append(instance_id)
    return inst


def _register_hand_asset(g, inv, card_id, cost=2):
    g.register_card_data(make_asset_data(id=card_id, cost=cost))
    inv.hand.append(card_id)


def _flood(g, loc_id, level):
    g.state.scenario.vars.setdefault("flood_levels", {})[loc_id] = level


def _emit(g, event, inv_id="player"):
    g.event_bus.emit(EventContext(game_state=g.state, event=event,
                                  investigator_id=inv_id))


class TestContract:
    def test_unknown_card_returns_none(self):
        g, ctrl = _mk()
        # 核心循环卡（如 ancient_evils）由核心分支处理，本模块不接管
        assert _resolve(ctrl, "ancient_evils") is None
        assert _resolve(ctrl, "not_a_card") is None


class TestInTooDeep:
    def test_blindsense_amalgam_in_play_engages_and_attacks(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inst = _add_enemy(g, "am1", "the_amalgam", traits=["deep one", "elite"],
                          damage=1, horror=1)
        inst.exhausted = True
        _fail_bag(g)
        r = _resolve(ctrl, "blindsense")
        assert r["message"] == "blindsense"
        assert "am1" in inv.threat_area
        assert inst.exhausted is False
        assert inv.damage == 1 and inv.horror == 1

    def test_blindsense_amalgam_in_depths_enters_play(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        g.register_card_data(make_enemy_data(id="the_amalgam", damage=1, horror=1))
        g.state.scenario.vars["the_depths"] = ["the_amalgam"]
        _fail_bag(g)
        _resolve(ctrl, "blindsense")
        assert g.state.scenario.vars["the_depths"] == []
        spawned = [i for i, ci in g.state.cards_in_play.items()
                   if ci.card_id == "the_amalgam"]
        assert spawned and spawned[0] in inv.threat_area
        assert inv.damage == 1 and inv.horror == 1

    def test_from_the_depths_spawns_from_depths(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        g.register_card_data(make_enemy_data(id="the_amalgam"))
        g.state.scenario.vars["the_depths"] = ["the_amalgam"]
        r = _resolve(ctrl, "from_the_depths")
        assert not r.get("surge")
        spawned = [i for i, ci in g.state.cards_in_play.items()
                   if ci.card_id == "the_amalgam"]
        assert spawned and spawned[0] in inv.threat_area
        assert g.state.scenario.vars["the_depths"] == []

    def test_from_the_depths_otherwise_sends_to_depths_and_surges(self):
        g, ctrl = _mk()
        _add_enemy(g, "am1", "the_amalgam", traits=["deep one", "elite"])
        r = _resolve(ctrl, "from_the_depths")
        assert r.get("surge") is True
        assert "am1" not in g.state.cards_in_play
        assert g.state.scenario.vars["the_depths"] == ["the_amalgam"]


class TestVanishingOfElinaHarper:
    def test_psychic_pull_discards_and_loses_action_on_fail(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        _register_hand_asset(g, inv, "cheap_gun", cost=2)
        _fail_bag(g)
        r = _resolve(ctrl, "psychic_pull")
        assert r["message"] == "psychic_pull"
        assert inv.hand == []
        assert "cheap_gun" in inv.discard
        assert inv.actions_remaining == 2

    def test_psychic_pull_surges_with_empty_hand(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.hand = []
        r = _resolve(ctrl, "psychic_pull")
        assert r.get("surge") is True


class TestDeepOneAssault:
    def test_disengage_then_engage_from_location_and_connections(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        _add_location(g, "loc_b")
        _connect(g, "test_location", "loc_b")
        _add_enemy(g, "e1", "deep_one_a", traits=["deep one"], engaged=True)
        _add_enemy(g, "e2", "deep_one_b", traits=["deep one"], location="loc_b")
        _add_enemy(g, "e3", "not_deep", traits=["monster"], location="loc_b")
        r = _resolve(ctrl, "deep_one_assault")
        assert r["message"] == "deep_one_assault"
        assert "e1" in inv.threat_area and "e2" in inv.threat_area
        assert "e3" in g.state.locations["loc_b"].enemies

    def test_no_deep_one_pulls_from_encounter_deck(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        g.register_card_data(make_enemy_data(id="lurking_deep_one"))
        cd = g.state.get_card_data("lurking_deep_one")
        cd.traits = ["deep one"]
        g.state.scenario.encounter_deck = ["lurking_deep_one"]
        _resolve(ctrl, "deep_one_assault")
        spawned = [i for i, ci in g.state.cards_in_play.items()
                   if ci.card_id == "lurking_deep_one"]
        assert spawned and spawned[0] in inv.threat_area
        assert "lurking_deep_one" not in g.state.scenario.encounter_deck


class TestFloodHazards:
    def test_undertow_surges_when_unflooded(self):
        g, ctrl = _mk()
        r = _resolve(ctrl, "undertow")
        assert r.get("surge") is True

    def test_undertow_in_threat_and_move_triggers_damage(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        _flood(g, "test_location", 1)
        _resolve(ctrl, "undertow")
        assert any(g.state.get_card_instance(i).card_id == "undertow"
                   for i in inv.threat_area)
        _emit(g, GameEvent.MOVE_ACTION_INITIATED)
        assert inv.damage == 2 and inv.horror == 2
        assert not any(g.state.get_card_instance(i) and
                       g.state.get_card_instance(i).card_id == "undertow"
                       for i in inv.threat_area)
        assert "undertow" in g.state.scenario.encounter_discard

    def test_undertow_fight_the_pull_discards_on_success(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        _flood(g, "test_location", 1)
        inv.hand = ["x"]
        _resolve(ctrl, "undertow")
        _pass_bag(g)  # 格斗3 vs 难度3 → 成功
        assert tic.activate_fight_the_pull(ctrl, "player", skill="combat") is True
        assert "x" in inv.discard
        assert inv.threat_area == []
        assert "undertow" in g.state.scenario.encounter_discard

    def test_rising_tides_increases_nearest_flood(self):
        g, ctrl = _mk()
        r = _resolve(ctrl, "rising_tides")
        assert r["message"] == "rising_tides"
        assert g.state.scenario.vars["flood_levels"]["test_location"] == 1

    def test_rising_tides_surges_when_all_fully_flooded(self):
        g, ctrl = _mk()
        _flood(g, "test_location", 2)
        r = _resolve(ctrl, "rising_tides")
        assert r.get("surge") is True

    def test_riptide_surges_when_unflooded(self):
        g, ctrl = _mk()
        assert _resolve(ctrl, "riptide").get("surge") is True

    def test_riptide_fail_discards_cheapest_asset(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        _flood(g, "test_location", 1)
        _add_asset(g, inv, "a1", "asset_a", cost=1)
        _fail_bag(g)
        _resolve(ctrl, "riptide")
        assert inv.play_area == []

    def test_riptide_fully_flooded_no_asset_loses_resources(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        _flood(g, "test_location", 2)  # 难度4，AUTO_FAIL → 差额4
        inv.resources = 5
        _fail_bag(g)
        _resolve(ctrl, "riptide")
        assert inv.resources == 1


class TestLairOfDagon:
    def test_fog_over_innsmouth_pending_then_success_put_in_play(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        r = _resolve(ctrl, "fog_over_innsmouth")
        assert r["pending"] is True
        pc = g.state.scenario.vars["pending_choice"]
        assert pc["investigator_id"] == "player"
        assert {o["id"] for o in pc["options"]} == {"take_horror", "put_in_play"}
        g.state.scenario.vars.pop("pending_choice")

        _pass_bag(g)  # 意志3 vs 3 → 成功
        r = _resolve(ctrl, "fog_over_innsmouth", choice="put_in_play")
        assert r["pending"] is False
        assert inv.horror == 0
        assert g.state.scenario.vars["next_to_agenda"]["fog_over_innsmouth"] == 1
        _emit(g, GameEvent.ROUND_ENDS)
        assert "fog_over_innsmouth" not in g.state.scenario.vars["next_to_agenda"]
        assert "fog_over_innsmouth" in g.state.scenario.encounter_discard

    def test_fog_over_innsmouth_fail_does_both(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        _fail_bag(g)
        _resolve(ctrl, "fog_over_innsmouth", choice="take_horror")
        assert inv.horror == 1
        assert g.state.scenario.vars["next_to_agenda"]["fog_over_innsmouth"] == 1

    def test_macabre_memento_cultist_token_auto_fails(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        g.chaos_bag.tokens = [ChaosTokenType.CULTIST]  # 本来+0会成功，但自动失败
        _resolve(ctrl, "macabre_memento")
        assert inv.horror == 2

    def test_macabre_memento_success_no_horror(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        _pass_bag(g)
        _resolve(ctrl, "macabre_memento")
        assert inv.horror == 0

    def test_fractured_consciousness_tablet_auto_fails(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        g.chaos_bag.tokens = [ChaosTokenType.TABLET]
        _resolve(ctrl, "fractured_consciousness")
        assert inv.damage == 2

    def test_memory_of_oblivion_discards_per_margin(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.hand = ["a", "b", "c"]
        _fail_bag(g)  # AUTO_FAIL → 差额4 → 弃光3张
        _resolve(ctrl, "memory_of_oblivion")
        assert inv.hand == []
        assert sorted(inv.discard) == ["a", "b", "c"]

    def test_malfunction_attaches_to_vehicle_and_fix_discards(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        _add_asset(g, inv, "car1", "thomas_dawsons_car", cost=3, traits=["vehicle"])
        r = _resolve(ctrl, "malfunction")
        assert r["message"] == "malfunction"
        records = g.state.scenario.vars["malfunction"]
        assert len(records) == 1
        mal_iid, target = next(iter(records.items()))
        assert target == "car1"
        assert g.state.get_card_instance(mal_iid).attached_to == "car1"

        inv.actions_remaining = 3
        _pass_bag(g)  # 智力3 vs 3 → 成功
        assert tic.activate_fix_malfunction(ctrl, "player") is True
        assert inv.actions_remaining == 2
        assert g.state.scenario.vars["malfunction"] == {}
        assert "malfunction" in g.state.scenario.encounter_discard

    def test_malfunction_no_vehicle_no_effect(self):
        g, ctrl = _mk()
        r = _resolve(ctrl, "malfunction")
        assert r["message"] == "malfunction"
        assert "malfunction" not in g.state.scenario.vars

    def test_tidal_alignment_floods_and_damages(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        r = _resolve(ctrl, "tidal_alignment")
        assert not r.get("surge")
        assert g.state.scenario.vars["flood_levels"]["test_location"] == 1
        assert inv.damage == 1

    def test_tidal_alignment_surges_at_full_flood(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        _flood(g, "test_location", 2)
        r = _resolve(ctrl, "tidal_alignment")
        assert r.get("surge") is True
        assert inv.damage == 1  # 伤害仍然结算

    def test_syzygy_pending_then_each_branch(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        r = _resolve(ctrl, "syzygy")
        assert r["pending"] is True
        pc = g.state.scenario.vars["pending_choice"]
        assert pc["investigator_id"] == "player"
        assert {o["id"] for o in pc["options"]} == {
            "lose_resources", "take_horror", "place_doom"}
        g.state.scenario.vars.pop("pending_choice")

        _resolve(ctrl, "syzygy", choice="take_horror")
        assert inv.horror == 2

        g2, ctrl2 = _mk()
        inv2 = g2.state.get_investigator("player")
        _resolve(ctrl2, "syzygy", choice="lose_resources")
        assert inv2.resources == 2

        g3, ctrl3 = _mk()
        _resolve(ctrl3, "syzygy", choice="place_doom")
        assert g3.state.scenario.doom_on_agenda == 1


class TestInnsmouthLookCards:
    def test_innsmouth_look_threat_sanity_and_intellect_penalty(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        r = _resolve(ctrl, "innsmouth_look")
        assert r["message"] == "innsmouth_look"
        assert any(g.state.get_card_instance(i).card_id == "innsmouth_look"
                   for i in inv.threat_area)
        assert inv.sanity == 6  # -1神智
        assert g.state.scenario.vars["deep_one_trait"]["player"] is True

        _pass_bag(g)
        res = g.skill_test_engine.run_test(
            investigator_id="player", skill_type=Skill.INTELLECT,
            difficulty=1, committed_card_ids=[])
        assert res.modified_skill == 2  # 智力3 - 1

        _pass_bag(g)  # 意志3 vs 3 → 成功
        assert tic.activate_discard_innsmouth_look(ctrl, "player") is True
        assert inv.threat_area == []
        assert inv.sanity == 7

    def test_furtive_locals_fail_does_both(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        r = _resolve(ctrl, "furtive_locals")
        assert r["pending"] is True
        g.state.scenario.vars.pop("pending_choice")
        _fail_bag(g)
        _resolve(ctrl, "furtive_locals", choice="take_damage")
        assert inv.damage == 1
        assert g.state.scenario.vars["next_to_agenda"]["furtive_locals"] == 1

    def test_furtive_locals_success_put_in_play_no_damage(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        _pass_bag(g)
        _resolve(ctrl, "furtive_locals", choice="put_in_play")
        assert inv.damage == 0
        assert g.state.scenario.vars["next_to_agenda"]["furtive_locals"] == 1


class TestHorrorInHighGear:
    def test_deep_one_invasion_spawns_hunter_at_east_location(self):
        g, ctrl = _mk()
        _add_location(g, "loc_east")
        g.state.scenario.vars["location_grid"] = {
            "test_location": (0, 0), "loc_east": (0, 1)}
        cd = make_enemy_data(id="hunting_deep_one", keywords=["hunter"])
        cd.traits = ["deep one"]
        g.register_card_data(cd)
        g.state.scenario.encounter_deck = ["hunting_deep_one"]
        g.state.scenario.encounter_discard = []
        r = _resolve(ctrl, "deep_one_invasion")
        assert r["message"] == "deep_one_invasion"
        spawned = [i for i, ci in g.state.cards_in_play.items()
                   if ci.card_id == "hunting_deep_one"]
        assert spawned
        assert spawned[0] in g.state.locations["loc_east"].enemies

    def test_pulled_back_moves_east_and_drops_keys(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        _add_location(g, "loc_east")
        g.state.scenario.vars["location_grid"] = {
            "test_location": (0, 0), "loc_east": (0, 1)}
        g.state.scenario.vars["keys"] = {"player": ["key_red"]}
        _fail_bag(g)
        _resolve(ctrl, "pulled_back")
        assert inv.location_id == "loc_east"
        assert g.state.scenario.vars["keys"]["player"] == []
        assert g.state.scenario.vars["location_keys"]["loc_east"] == ["key_red"]

    def test_inundated_places_barriers_then_surges(self):
        g, ctrl = _mk()
        _add_location(g, "loc_b")
        _add_location(g, "loc_c")
        g.state.locations["test_location"].card_data.connections = ["loc_b", "loc_c"]
        r = _resolve(ctrl, "inundated")
        assert not r.get("surge")
        barriers = g.state.scenario.vars["barriers"]
        assert ["test_location", "loc_b"] in barriers
        assert ["test_location", "loc_c"] in barriers
        r2 = _resolve(ctrl, "inundated")
        assert r2.get("surge") is True


class TestDevilReef:
    def test_shapes_in_the_water_fail_two_horror(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        _flood(g, "test_location", 2)  # 难度2+2
        _fail_bag(g)
        _resolve(ctrl, "shapes_in_the_water")
        assert inv.horror == 2

    def test_aquatic_ambush_next_to_agenda_until_round_end(self):
        g, ctrl = _mk()
        _resolve(ctrl, "aquatic_ambush")
        assert g.state.scenario.vars["next_to_agenda"]["aquatic_ambush"] == 1
        _emit(g, GameEvent.ROUND_ENDS)
        assert "aquatic_ambush" not in g.state.scenario.vars["next_to_agenda"]
        assert "aquatic_ambush" in g.state.scenario.encounter_discard

    def test_horrors_from_the_deep_fail_two_damage(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        _flood(g, "test_location", 1)  # 难度2+1
        _fail_bag(g)
        _resolve(ctrl, "horrors_from_the_deep")
        assert inv.damage == 2

    def test_stowaway_surges_without_vehicles(self):
        g, ctrl = _mk()
        assert _resolve(ctrl, "stowaway").get("surge") is True

    def test_stowaway_damages_riders(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        g.state.scenario.vars["vehicles"] = {
            "player": {"vehicle": "fishing_vessel", "driver": True}}
        _resolve(ctrl, "stowaway")
        assert inv.damage == 1 and inv.horror == 1

    def test_dragged_under_leaves_vehicle_and_discards_via_action(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        g.state.scenario.vars["vehicles"] = {
            "player": {"vehicle": "fishing_vessel", "driver": True}}
        _resolve(ctrl, "dragged_under")
        assert g.state.scenario.vars["vehicles"] == {}
        assert any(g.state.get_card_instance(i).card_id == "dragged_under"
                   for i in inv.threat_area)
        assert g.state.scenario.vars["cannot_enter_vehicles"]["player"] is True

        inv.actions_remaining = 3
        _pass_bag(g)  # 敏捷3 vs 3 → 成功
        assert tic.activate_discard_dragged_under(ctrl, "player", skill="agility") is True
        assert inv.actions_remaining == 2
        assert inv.threat_area == []
        assert "player" not in g.state.scenario.vars["cannot_enter_vehicles"]


class TestVehicleHazards:
    def test_bumpy_ride_on_foot_fail_three_damage(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        _fail_bag(g)
        _resolve(ctrl, "bumpy_ride")
        assert inv.damage == 3

    def test_bumpy_ride_in_vehicle_driver_fail_two_damage_each(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        g.state.scenario.vars["vehicles"] = {
            "player": {"vehicle": "car", "driver": True}}
        _fail_bag(g)
        _resolve(ctrl, "bumpy_ride")
        assert inv.damage == 2

    def test_i_cant_see_on_foot_fail_three_horror(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        _fail_bag(g)
        _resolve(ctrl, "i_cant_see")
        assert inv.horror == 3

    def test_i_cant_see_in_vehicle_driver_fail_two_horror_each(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        g.state.scenario.vars["vehicles"] = {
            "player": {"vehicle": "car", "driver": True}}
        _fail_bag(g)
        _resolve(ctrl, "i_cant_see")
        assert inv.horror == 2

    def test_eyes_in_the_trees_fail_discards_asset_and_hits_passengers(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        g.add_investigator("player2", make_investigator_data(id="inv2"),
                           starting_location="test_location")
        inv2 = g.state.get_investigator("player2")
        _add_asset(g, inv, "a1", "asset_a", cost=1)
        inv2.hand = ["x", "y"]
        g.state.scenario.vars["vehicles"] = {
            "player": {"vehicle": "car", "driver": True},
            "player2": {"vehicle": "car", "driver": False},
        }
        _fail_bag(g)  # 意志3 vs 4 AUTO_FAIL → 差额4
        _resolve(ctrl, "eyes_in_the_trees")
        assert inv.play_area == []          # 玩家弃掉最便宜支援
        assert inv2.hand == []              # 同载具乘客按差额弃手牌
        assert sorted(inv2.discard) == ["x", "y"]

    def test_theyre_catching_up_moves_hunter(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        _add_location(g, "loc_b")
        _connect(g, "test_location", "loc_b")
        _add_enemy(g, "h1", "pursuing_motorcar", keywords=["hunter"],
                   traits=["vehicle"], location="loc_b")
        r = _resolve(ctrl, "theyre_catching_up")
        assert r["message"] == "theyre_catching_up"
        assert "h1" in inv.threat_area  # 移动一步后进入玩家地点并交战

    def test_theyre_catching_up_no_move_digs_vehicle_enemy(self):
        g, ctrl = _mk()
        cd = make_enemy_data(id="hit_van")
        cd.traits = ["vehicle"]
        g.register_card_data(cd)
        g.state.scenario.encounter_deck = ["hit_van"]
        _resolve(ctrl, "theyre_catching_up")
        spawned = [i for i, ci in g.state.cards_in_play.items()
                   if ci.card_id == "hit_van"]
        # 无 grid 配置 → 最后方地点回退为抽卡调查员所在地点（未交战生成）
        assert spawned and spawned[0] in g.state.locations["test_location"].enemies


class TestLightInTheFog:
    def test_hideous_lullaby_surges_without_deep_ones(self):
        g, ctrl = _mk()
        assert _resolve(ctrl, "hideous_lullaby").get("surge") is True

    def test_hideous_lullaby_difficulty_from_highest_fight(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        _add_enemy(g, "d1", "deep_one_bull", traits=["deep one"], fight=4)
        _fail_bag(g)
        _resolve(ctrl, "hideous_lullaby")
        assert inv.horror == 2

    def test_kiss_of_brine_fail_then_discards_at_enemy_phase_end(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        _flood(g, "test_location", 1)  # 难度2+2=4
        _fail_bag(g)
        _resolve(ctrl, "kiss_of_brine")
        assert inv.damage == 1
        assert any(g.state.get_card_instance(i).card_id == "kiss_of_brine"
                   for i in inv.threat_area)
        _emit(g, GameEvent.ENEMY_PHASE_ENDS)
        assert inv.threat_area == []
        assert "kiss_of_brine" in g.state.scenario.encounter_discard

    def test_totality_horror_on_entering_flooded_and_discard_at_turn_end(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        _add_location(g, "loc_b")
        _flood(g, "loc_b", 1)
        _fail_bag(g)
        _resolve(ctrl, "totality")
        assert any(g.state.get_card_instance(i).card_id == "totality"
                   for i in inv.threat_area)
        inv.location_id = "loc_b"  # 移动后（AFTER 语义）
        _emit(g, GameEvent.MOVE_ACTION_INITIATED)
        assert inv.horror == 1
        _emit(g, GameEvent.INVESTIGATOR_TURN_ENDS)
        assert inv.threat_area == []
        assert "totality" in g.state.scenario.encounter_discard

    def test_worth_his_salt_records_attachment_target(self):
        g, ctrl = _mk()
        r = _resolve(ctrl, "worth_his_salt")
        assert r["message"] == "worth_his_salt"
        assert g.state.scenario.vars["worth_his_salt"] == "absent"

        g2, ctrl2 = _mk()
        _add_enemy(g2, "oc1", "oceiros_marsh", traits=["deep one", "elite"])
        _resolve(ctrl2, "worth_his_salt")
        assert g2.state.scenario.vars["worth_his_salt"] == "oc1"

    def test_taken_captive_captures_and_drops_keys_on_holding_cells(self):
        g, ctrl = _mk()
        g.state.scenario.vars["keys"] = {"player": ["key_red", "key_blue"]}
        _fail_bag(g)
        _resolve(ctrl, "taken_captive")
        assert g.state.scenario.vars["captured"]["player"] is True
        assert g.state.scenario.vars["keys"]["player"] == []
        assert g.state.scenario.vars["location_keys"]["holding_cells"] == [
            "key_red", "key_blue"]


class TestIntoTheMaelstrom:
    def test_fulfill_the_oaths_act1_single_test(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        g.state.scenario.current_act_index = 0
        _fail_bag(g)
        _resolve(ctrl, "fulfill_the_oaths")
        assert inv.damage == 1

    def test_fulfill_the_oaths_act3_three_tests(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        g.state.scenario.current_act_index = 2  # act 3
        _fail_bag(g)
        _resolve(ctrl, "fulfill_the_oaths")
        assert inv.damage == 3

    def test_secret_gathering_adds_curse_doom_and_double_horror(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inst = _add_enemy(g, "c1", "priest_of_dagon", traits=["cultist"])
        g.chaos_bag.tokens = [ChaosTokenType.CURSE]  # -2 → 意志1 vs 4 失败
        _resolve(ctrl, "secret_gathering")
        assert inst.doom == 1
        assert inv.horror == 2  # 检定期间抽出诅咒 → 2恐惧
        curses = [t for t in g.chaos_bag.tokens if t == ChaosTokenType.CURSE]
        assert len(curses) == 2  # 1个原本 + 1个卡牌效果加入

    def test_secret_gathering_fail_without_curse_one_horror(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inst = _add_enemy(g, "c1", "priest_of_dagon", traits=["cultist"])
        # 卡牌效果会先向袋中加1诅咒；seed(1) 使抽取固定命中 index0 的 -1（不抽诅咒）
        g.chaos_bag.tokens = [ChaosTokenType.MINUS_1]
        g.chaos_bag.seed(1)  # 意志2 vs 4 失败
        _resolve(ctrl, "secret_gathering")
        assert inst.doom == 1
        assert inv.horror == 1

    def test_esoteric_ritual_fail_discards_two_cards(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.hand = ["a", "b", "c"]
        _fail_bag(g)
        _resolve(ctrl, "esoteric_ritual")
        assert inv.hand == ["c"]
        assert sorted(inv.discard) == ["a", "b"]

    def test_esoteric_ritual_curse_does_both(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.hand = ["a", "b", "c"]
        _add_asset(g, inv, "a1", "asset_a", cost=1)
        g.chaos_bag.tokens = [ChaosTokenType.CURSE]  # -2 → 失败且抽出诅咒
        _resolve(ctrl, "esoteric_ritual")
        assert inv.hand == ["c"]
        assert inv.play_area == []

    def test_heralds_of_the_deep_adds_curses_per_margin(self):
        g, ctrl = _mk()
        _fail_bag(g)  # AUTO_FAIL → 差额3
        r = _resolve(ctrl, "heralds_of_the_deep")
        assert not r.get("surge")
        curses = [t for t in g.chaos_bag.tokens if t == ChaosTokenType.CURSE]
        assert len(curses) == 3

    def test_heralds_of_the_deep_surges_when_bag_full_of_bless_curse(self):
        g, ctrl = _mk()
        # 祝福+诅咒已达10个上限 → 无法加入 → 涌动
        g.chaos_bag.tokens = [ChaosTokenType.CURSE] * 10  # 抽出诅咒-2 → 意志1 vs 3 失败
        r = _resolve(ctrl, "heralds_of_the_deep")
        assert r.get("surge") is True
        curses = [t for t in g.chaos_bag.tokens if t == ChaosTokenType.CURSE]
        assert len(curses) == 10

    def test_stone_barrier_attaches_and_exhausts_via_action(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        r = _resolve(ctrl, "stone_barrier")
        assert not r.get("surge")
        iid = ctrl.location_attachment_instance("test_location", "stone_barrier")
        assert iid is not None

        inv.actions_remaining = 3
        _pass_bag(g)  # 敏捷3 vs 1 → 成功
        assert tic.activate_exhaust_stone_barrier(ctrl, "player", skill="agility") is True
        assert inv.actions_remaining == 2
        assert g.state.get_card_instance(iid).exhausted is True

    def test_stone_barrier_surges_when_location_flooded(self):
        g, ctrl = _mk()
        _flood(g, "test_location", 1)
        r = _resolve(ctrl, "stone_barrier")
        assert r.get("surge") is True
        assert ctrl.location_attachment_instance("test_location", "stone_barrier")

    def test_treacherous_depths_pending_then_increase_flood(self):
        g, ctrl = _mk()
        r = _resolve(ctrl, "treacherous_depths")
        assert r["pending"] is True
        pc = g.state.scenario.vars["pending_choice"]
        assert pc["investigator_id"] == "player"
        g.state.scenario.vars.pop("pending_choice")
        _resolve(ctrl, "treacherous_depths", choice="increase_flood")
        assert g.state.scenario.vars["flood_levels"]["test_location"] == 1

    def test_treacherous_depths_discard_assets_branch(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        _add_asset(g, inv, "a1", "asset_a", cost=2)  # 地点隐蔽2 → 费用满足
        _resolve(ctrl, "treacherous_depths", choice="discard_assets")
        assert inv.play_area == []
        assert "flood_levels" not in g.state.scenario.vars

    def test_treacherous_depths_insufficient_assets_falls_back_to_flood(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        _add_asset(g, inv, "a1", "asset_a", cost=1)  # 费用1 < 隐蔽2
        _resolve(ctrl, "treacherous_depths", choice="discard_assets")
        assert inv.play_area == ["a1"]  # 未弃
        assert g.state.scenario.vars["flood_levels"]["test_location"] == 1

    def test_conspiracy_of_deep_ones_ancient_one_attacks(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        _add_location(g, "sanctum_loc", traits=["sanctum"])
        g.state.scenario.vars["location_keys"] = {"sanctum_loc": ["key_red"]}
        _add_enemy(g, "ao1", "dagon_a", traits=["ancient one"], damage=2, horror=1)
        _fail_bag(g)  # 难度2+1=3，AUTO_FAIL
        _resolve(ctrl, "conspiracy_of_deep_ones")
        assert inv.damage == 2 and inv.horror == 1
        assert g.state.scenario.doom_on_agenda == 0

    def test_conspiracy_of_deep_ones_no_ancient_one_places_doom(self):
        g, ctrl = _mk()
        _fail_bag(g)
        _resolve(ctrl, "conspiracy_of_deep_ones")
        assert g.state.scenario.doom_on_agenda == 1

    def test_thalassophobia_surges_when_nobody_flooded(self):
        g, ctrl = _mk()
        assert _resolve(ctrl, "thalassophobia").get("surge") is True

    def test_thalassophobia_partial_and_full_flood(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        _flood(g, "test_location", 1)
        _resolve(ctrl, "thalassophobia")
        assert inv.horror == 1

        g2, ctrl2 = _mk()
        inv2 = g2.state.get_investigator("player")
        _flood(g2, "test_location", 2)
        _resolve(ctrl2, "thalassophobia")
        assert inv2.horror == 1  # 直接恐惧（不可防止）
