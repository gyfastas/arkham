"""Tests for Edge of the Earth encounter treachery effects."""

from __future__ import annotations

from backend.engine.event_bus import EventContext
from backend.models.enums import CardType, ChaosTokenType, GameEvent, Skill
from backend.models.state import CardData, CardInstance
from backend.scenarios import encounters_edge_of_the_earth as ee
from backend.tests.conftest import make_asset_data, make_enemy_data, make_location_data
from backend.tests.test_scenario_tokens import _add_enemy, _make_game


def _mk(scenario_id="ice_and_death_part_1"):
    return _make_game(scenario_id)


def _fail_bag(g):
    """Force the next skill test to fail (auto_fail → margin = difficulty)."""
    g.chaos_bag.tokens = [ChaosTokenType.AUTO_FAIL]


def _pass_bag(g):
    g.chaos_bag.tokens = [ChaosTokenType.ZERO]


def _frost_bag(g):
    g.chaos_bag.tokens = [ChaosTokenType.FROST]


def _resolve(ctrl, card_id, inv_id="player", choice=None):
    return ee.resolve_treachery(ctrl, card_id, investigator_id=inv_id, choice=choice)


def _register_treachery(g, card_id, traits=None):
    g.register_card_data(CardData(id=card_id, name=card_id, name_cn=card_id,
                                  type=CardType.TREACHERY, traits=traits or []))


def _register_asset(g, card_id, cost=0, traits=None, health=None, sanity=None,
                    text=""):
    cd = make_asset_data(id=card_id, cost=cost, health=health, sanity=sanity)
    cd.traits = traits or []
    cd.text = text
    g.register_card_data(cd)
    return cd


def _add_asset_instance(g, inv, instance_id, card_id):
    inst = CardInstance(instance_id=instance_id, card_id=card_id,
                        owner_id="player", controller_id="player")
    g.state.cards_in_play[instance_id] = inst
    inv.play_area.append(instance_id)
    return inst


def _add_location(g, location_id, *, shroud=2, connections=None, clues=0):
    data = make_location_data(id=location_id, shroud=shroud,
                              connections=connections or [])
    g.register_card_data(data)
    return g.add_location(location_id, data, clues=clues)


def _turn_end(g, inv_id="player"):
    g.event_bus.emit(EventContext(
        game_state=g.state, event=GameEvent.INVESTIGATOR_TURN_ENDS,
        investigator_id=inv_id))


def _round_end(g):
    g.event_bus.emit(EventContext(game_state=g.state, event=GameEvent.ROUND_ENDS))


class TestIceAndDeath:
    def test_apeirophobia_fail_horror_per_margin(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.card_data.skills.willpower = 1
        g.state.scenario.vars["location_shelter"] = {"test_location": 3}
        _fail_bag(g)  # margin = 3
        r = _resolve(ctrl, "apeirophobia")
        assert r["message"] == "apeirophobia"
        assert inv.horror == 3

    def test_apeirophobia_success_no_horror(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.card_data.skills.willpower = 5
        g.state.scenario.vars["location_shelter"] = {"test_location": 3}
        _pass_bag(g)
        _resolve(ctrl, "apeirophobia")
        assert inv.horror == 0

    def test_zero_visibility_enters_threat_and_discards_on_success(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        _resolve(ctrl, "zero_visibility")
        assert any(g.state.cards_in_play[i].card_id == "zero_visibility"
                   for i in inv.threat_area)
        assert g.state.scenario.vars["zero_visibility"]["player"] is True
        _pass_bag(g)  # 敏捷3 vs 2 → 成功
        _turn_end(g)
        assert not any(i in g.state.cards_in_play
                       and g.state.cards_in_play[i].card_id == "zero_visibility"
                       for i in inv.threat_area)
        assert "zero_visibility" in g.state.scenario.encounter_discard
        assert "player" not in g.state.scenario.vars["zero_visibility"]

    def test_zero_visibility_failed_test_stays(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.card_data.skills.agility = 1
        _resolve(ctrl, "zero_visibility")
        _fail_bag(g)
        _turn_end(g)
        assert any(g.state.cards_in_play[i].card_id == "zero_visibility"
                   for i in inv.threat_area)


class TestSeepingNightmaresAndMirage:
    def test_phantasmagoria_surges_without_nightmare(self):
        g, ctrl = _mk()
        r = _resolve(ctrl, "phantasmagoria")
        assert r.get("surge") is True

    def test_phantasmagoria_spawns_card_beneath(self):
        g, ctrl = _mk()
        g.register_card_data(make_enemy_data(id="seeping_nightmare"))
        g.register_card_data(make_enemy_data(id="horrifying_shade"))
        _add_enemy(g, "sn1", "seeping_nightmare", ["monster", "eidolon", "elite"])
        g.state.scenario.vars["cards_beneath"] = {"sn1": ["horrifying_shade"]}
        r = _resolve(ctrl, "phantasmagoria")
        assert r.get("surge") is None
        loc = g.state.get_location("test_location")
        spawned = [i for i, inst in g.state.cards_in_play.items()
                   if inst.card_id == "horrifying_shade"]
        assert spawned and spawned[0] in loc.enemies
        assert g.state.scenario.vars["cards_beneath"]["sn1"] == []

    def test_phantasmagoria_no_beneath_engages_and_attacks(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        g.register_card_data(make_enemy_data(id="seeping_nightmare"))
        _add_enemy(g, "sn1", "seeping_nightmare", ["monster", "eidolon", "elite"],
                   location="test_location")
        _resolve(ctrl, "phantasmagoria")
        assert "sn1" in inv.threat_area
        assert inv.damage == 1 and inv.horror == 1  # 默认敌人1伤1恐

    def test_evanescent_mist_attach_clues_and_discard_when_cleared(self):
        g, ctrl = _mk()
        loc = g.state.get_location("test_location")
        clues0 = loc.clues
        r = _resolve(ctrl, "evanescent_mist")
        assert r["message"] == "evanescent_mist"
        assert ctrl.location_attachment_instance("test_location", "evanescent_mist")
        assert loc.clues == clues0 + 2
        g.state.scenario.vars["mirage_cleared"] = {"test_location": True}
        _round_end(g)
        assert ctrl.location_attachment_instance("test_location", "evanescent_mist") is None

    def test_anamnesis_pending_then_place_doom(self):
        g, ctrl = _mk()
        r = _resolve(ctrl, "anamnesis")
        assert r["pending"] is True
        pc = g.state.scenario.vars["pending_choice"]
        assert pc["investigator_id"] == "player"
        g.state.scenario.vars.pop("pending_choice")
        doom0 = g.state.scenario.doom_on_agenda
        r = _resolve(ctrl, "anamnesis", choice="place_doom")
        assert r["pending"] is False
        assert g.state.scenario.doom_on_agenda == doom0 + 1

    def test_anamnesis_take_horror(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        _resolve(ctrl, "anamnesis", choice="take_horror")
        assert inv.horror == 2


class TestForbiddenPeaks:
    def test_snowfall_places_two_clues(self):
        g, ctrl = _mk()
        loc = g.state.get_location("test_location")
        clues0 = loc.clues
        _resolve(ctrl, "snowfall")
        assert loc.clues == clues0 + 2

    def test_avalanche_surges_when_cannot_move(self):
        g, ctrl = _mk()
        # 默认无高度数据 → level 0 → 涌动
        r = _resolve(ctrl, "avalanche")
        assert r.get("surge") is True

    def test_avalanche_moves_down_on_fail_then_stops(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.card_data.skills.willpower = 3
        _add_location(g, "below_loc", connections=["test_location"])
        g.state.scenario.vars["location_levels"] = {"test_location": 2, "below_loc": 1}
        g.state.scenario.vars["location_below"] = {"test_location": "below_loc"}
        g.chaos_bag.tokens = [ChaosTokenType.MINUS_1]
        # 第1次：移到 below_loc，检定难度1：3-1=2 ≥ 1 成功 → 停止
        r = _resolve(ctrl, "avalanche")
        assert r.get("surge") is None
        assert inv.location_id == "below_loc"

    def test_hanging_on_the_edge_fail_drops_expedition_and_moves(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.card_data.skills.agility = 1
        _register_asset(g, "wooden_sledge", traits=["item", "expedition"])
        _register_asset(g, "knife", traits=["item", "weapon"])
        _add_asset_instance(g, inv, "a1", "wooden_sledge")
        _add_asset_instance(g, inv, "a2", "knife")
        _add_location(g, "below_loc")
        g.state.scenario.vars["location_levels"] = {"test_location": 3, "below_loc": 2}
        g.state.scenario.vars["location_below"] = {"test_location": "below_loc"}
        _fail_bag(g)
        _resolve(ctrl, "hanging_on_the_edge")
        assert inv.damage == 2
        assert "a1" not in inv.play_area and "a2" in inv.play_area
        dropped = g.state.scenario.vars["dropped_expedition_assets"]
        # 掉落在坠落前所在地点（test_location）
        assert dropped.get("test_location") == ["wooden_sledge"]
        assert inv.location_id == "below_loc"

    def test_hypothermia_fail_horror_per_margin(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.card_data.skills.willpower = 1
        _fail_bag(g)  # margin = 3
        _resolve(ctrl, "hypothermia")
        assert inv.horror == 3


class TestCityOfTheElderThings:
    def test_dawning_of_the_truth_no_keys_two_horror(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.card_data.skills.willpower = 1
        _fail_bag(g)  # 难度2，margin 2 → 2恐惧
        _resolve(ctrl, "dawning_of_the_truth")
        assert inv.horror == 2

    def test_dawning_of_the_truth_keys_raise_difficulty_and_horror(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.card_data.skills.willpower = 1
        g.state.scenario.vars["keys_on_location"] = {"test_location": 2}
        _fail_bag(g)  # 难度 2+2=4，margin 4 ≥ 3 → 3恐惧
        _resolve(ctrl, "dawning_of_the_truth")
        assert inv.horror == 3

    def test_crumbling_ruins_damage_per_margin(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.card_data.skills.agility = 1
        _fail_bag(g)  # margin = 3
        _resolve(ctrl, "crumbling_ruins")
        assert inv.damage == 3

    def test_frostbitten_frost_token_damage_once_per_test(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        _resolve(ctrl, "frostbitten")
        assert any(g.state.cards_in_play[i].card_id == "frostbitten"
                   for i in inv.threat_area)
        # 同一次检定揭示两次 frost（模拟）→ 只受1次
        for _ in range(2):
            g.event_bus.emit(EventContext(
                game_state=g.state, event=GameEvent.CHAOS_TOKEN_RESOLVED,
                investigator_id="player", chaos_token=ChaosTokenType.FROST))
        assert inv.damage == 1
        # 新一次检定开始 → 重置
        g.event_bus.emit(EventContext(
            game_state=g.state, event=GameEvent.SKILL_TEST_BEGINS,
            investigator_id="player", skill_type=Skill.AGILITY, difficulty=3))
        g.event_bus.emit(EventContext(
            game_state=g.state, event=GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="player", chaos_token=ChaosTokenType.FROST))
        assert inv.damage == 2

    def test_possessed_frost_token_horror(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        _resolve(ctrl, "possessed")
        g.event_bus.emit(EventContext(
            game_state=g.state, event=GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="player", chaos_token=ChaosTokenType.FROST))
        assert inv.horror == 1
        # 非 frost 标记不触发
        g.event_bus.emit(EventContext(
            game_state=g.state, event=GameEvent.SKILL_TEST_BEGINS,
            investigator_id="player", skill_type=Skill.WILLPOWER, difficulty=2))
        g.event_bus.emit(EventContext(
            game_state=g.state, event=GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="player", chaos_token=ChaosTokenType.SKULL))
        assert inv.horror == 1


class TestHeartOfMadness:
    def _with_gate(self, g):
        _add_location(g, "mid_loc", connections=["test_location"])
        gate_data = make_location_data(id="the_gate_of_yquaa", connections=["mid_loc"])
        g.register_card_data(gate_data)
        g.add_location("gate_loc", gate_data)
        # 修正连接：test_location → mid_loc → gate_loc
        g.state.locations["test_location"].card_data.connections = ["mid_loc"]

    def test_primeval_terror_distance_scales_difficulty(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.card_data.skills.willpower = 2
        self._with_gate(g)
        _fail_bag(g)  # 距离2 → 难度4；虽然auto_fail，伤害固定2
        _resolve(ctrl, "primeval_terror")
        assert inv.horror == 2

    def test_primeval_terror_success_no_horror(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.card_data.skills.willpower = 6
        _pass_bag(g)  # 无门 → 难度2；6 ≥ 2 成功
        _resolve(ctrl, "primeval_terror")
        assert inv.horror == 0

    def test_roots_of_the_earth_fail_two_damage(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.card_data.skills.agility = 1
        _fail_bag(g)
        _resolve(ctrl, "roots_of_the_earth")
        assert inv.damage == 2


class TestGreatSealAndAgents:
    def test_electrostatic_discharge_activated_seal(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        g.state.scenario.vars["seals"] = {"test_location": {"activated": True}}
        r = _resolve(ctrl, "electrostatic_discharge")
        assert r.get("surge") is True
        assert inv.horror == 1 and inv.damage == 1

    def test_electrostatic_discharge_dormant_seal_horror_only(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        g.state.scenario.vars["seals"] = {"test_location": {"activated": False}}
        r = _resolve(ctrl, "electrostatic_discharge")
        assert r.get("surge") is True
        assert inv.horror == 1 and inv.damage == 0

    def test_the_madness_within_shuffles_tekeli_and_horror_overflow(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.card_data.skills.willpower = 1
        g.state.scenario.vars["tekeli_li_deck"] = ["tekeli_li_a", "tekeli_li_b"]
        _fail_bag(g)  # margin 4，牌堆只有2张 → 混洗2张 + 2恐惧
        _resolve(ctrl, "the_madness_within")
        assert sorted(inv.deck) == ["tekeli_li_a", "tekeli_li_b"]
        assert g.state.scenario.vars["tekeli_li_deck"] == []
        assert inv.horror == 2


class TestCreaturesInTheIceAndWeather:
    def test_kindred_mist_attach_and_round_end_discard(self):
        g, ctrl = _mk()
        r = _resolve(ctrl, "kindred_mist")
        assert r["message"] == "kindred_mist"
        assert ctrl.location_attachment_instance("test_location", "kindred_mist")
        assert g.state.scenario.vars["kindred_mist"]["location_id"] == "test_location"
        _round_end(g)
        assert ctrl.location_attachment_instance("test_location", "kindred_mist") is None
        assert "kindred_mist" not in g.state.scenario.vars

    def test_kindred_mist_draws_tekeli_instead_of_shuffle(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.card_data.skills.willpower = 1
        _resolve(ctrl, "kindred_mist")
        g.state.scenario.vars["tekeli_li_deck"] = ["tekeli_li_c"]
        _fail_bag(g)  # margin 4，只有1张 → 入手1张 + 3恐惧
        _resolve(ctrl, "the_madness_within")
        assert "tekeli_li_c" in inv.hand
        assert "tekeli_li_c" not in inv.deck
        assert inv.horror == 3

    def test_antarctic_wind_attach_and_round_end_discard(self):
        g, ctrl = _mk()
        _resolve(ctrl, "antarctic_wind")
        assert ctrl.location_attachment_instance("test_location", "antarctic_wind")
        assert g.state.scenario.vars["antarctic_wind"]["test_location"] is True
        _round_end(g)
        assert ctrl.location_attachment_instance("test_location", "antarctic_wind") is None
        assert g.state.scenario.vars["antarctic_wind"] == {}

    def test_whiteout_debuffs_skills_until_round_end(self):
        g, ctrl = _mk()
        _resolve(ctrl, "whiteout")
        assert ctrl.location_attachment_instance("test_location", "whiteout")

        def _probe():
            ctx = EventContext(
                game_state=g.state, event=GameEvent.SKILL_VALUE_DETERMINED,
                investigator_id="player", skill_type=Skill.WILLPOWER,
                modified_skill=3, amount=3)
            g.event_bus.emit(ctx)
            return ctx.amount

        assert _probe() == 2
        _round_end(g)
        assert ctrl.location_attachment_instance("test_location", "whiteout") is None
        assert _probe() == 3

    def test_polar_vortex_turn_end_direct_damage(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        _register_asset(g, "ally_a", health=2)
        asset = _add_asset_instance(g, inv, "a1", "ally_a")
        _resolve(ctrl, "polar_vortex")
        _turn_end(g)
        assert inv.damage == 1  # 直接伤害
        assert asset.damage == 1
        _round_end(g)
        assert ctrl.location_attachment_instance("test_location", "polar_vortex") is None


class TestElderThingsAndHazards:
    def test_rise_of_the_elder_things_spawns_from_discard(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        g.register_card_data(make_enemy_data(id="elder_thing_scavenger"))
        g.state.get_card_data("elder_thing_scavenger").traits = ["monster", "elder thing"]
        _register_treachery(g, "filler")
        g.state.scenario.encounter_discard = ["filler", "elder_thing_scavenger"]
        r = _resolve(ctrl, "rise_of_the_elder_things")
        assert r.get("surge") is None
        spawned = [i for i, inst in g.state.cards_in_play.items()
                   if inst.card_id == "elder_thing_scavenger"]
        assert spawned and spawned[0] in inv.threat_area
        assert "elder_thing_scavenger" not in g.state.scenario.encounter_discard
        assert "rise_of_the_elder_things_round" in g.state.scenario.vars

    def test_rise_of_the_elder_things_surges_with_empty_discard(self):
        g, ctrl = _mk()
        r = _resolve(ctrl, "rise_of_the_elder_things")
        assert r.get("surge") is True

    def test_ice_shaft_frost_plus_fail_damage(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        # 敏捷3 vs 3，frost=-1 → 失败：2伤害 + frost 1伤害
        _frost_bag(g)
        _resolve(ctrl, "ice_shaft")
        assert inv.damage == 3

    def test_ice_shaft_success_only_frost_damage(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.card_data.skills.agility = 5
        _frost_bag(g)  # 5-1=4 ≥ 3 成功 → 仅 frost 1伤害
        _resolve(ctrl, "ice_shaft")
        assert inv.damage == 1

    def test_ice_shaft_no_frost_no_extra_damage(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.card_data.skills.agility = 5
        _pass_bag(g)
        _resolve(ctrl, "ice_shaft")
        assert inv.damage == 0

    def test_through_the_ice_failed_move_test(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.card_data.skills.agility = 1
        _resolve(ctrl, "through_the_ice")
        assert ctrl.location_attachment_instance("test_location", "through_the_ice")
        _fail_bag(g)
        g.event_bus.emit(EventContext(
            game_state=g.state, event=GameEvent.MOVE_ACTION_INITIATED,
            investigator_id="player", location_id="elsewhere"))
        assert inv.damage == 1 and inv.horror == 1
        assert ctrl.location_attachment_instance("test_location", "through_the_ice") is None

    def test_through_the_ice_passed_move_test_stays(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        _resolve(ctrl, "through_the_ice")
        _pass_bag(g)  # 敏捷3 vs 2 成功
        g.event_bus.emit(EventContext(
            game_state=g.state, event=GameEvent.MOVE_ACTION_INITIATED,
            investigator_id="player", location_id="elsewhere"))
        assert inv.damage == 0 and inv.horror == 0
        assert ctrl.location_attachment_instance("test_location", "through_the_ice")


class TestLeftBehindAndNamelessHorrors:
    def test_abandoned_to_madness_attach_and_doom_in_play(self):
        g, ctrl = _mk()
        e = _add_enemy(g, "e1", "lost_researcher", ["humanoid", "possessed"])
        r = _resolve(ctrl, "abandoned_to_madness")
        assert r["message"] == "abandoned_to_madness"
        assert e.doom == 1
        attached = [inst for inst in g.state.cards_in_play.values()
                    if inst.card_id == "abandoned_to_madness" and inst.attached_to == "e1"]
        assert attached
        assert g.state.scenario.vars["abandoned_to_madness"]["enemy"] == "e1"

    def test_abandoned_to_madness_pulls_from_encounter_deck(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        g.register_card_data(make_enemy_data(id="frenzied_explorer"))
        g.state.get_card_data("frenzied_explorer").traits = ["humanoid", "possessed"]
        _register_treachery(g, "filler")
        g.state.scenario.encounter_deck = ["filler", "frenzied_explorer"]
        _resolve(ctrl, "abandoned_to_madness")
        target = g.state.scenario.vars["abandoned_to_madness"]["enemy"]
        inst = g.state.get_card_instance(target)
        assert inst.card_id == "frenzied_explorer"
        assert target in inv.threat_area
        assert inst.doom == 1

    def test_blasphemous_visions_shuffle_and_activate_discard(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        g.state.scenario.vars["tekeli_li_deck"] = ["tekeli_li_d"]
        _resolve(ctrl, "blasphemous_visions")
        assert "tekeli_li_d" in inv.deck
        assert any(g.state.cards_in_play[i].card_id == "blasphemous_visions"
                   for i in inv.threat_area)
        _pass_bag(g)  # 意志3 vs 3 → 成功
        assert ee.activate_discard_blasphemous_visions(ctrl, "player") is True
        assert inv.actions_remaining == 2
        assert not any(i in g.state.cards_in_play
                       and g.state.cards_in_play[i].card_id == "blasphemous_visions"
                       for i in inv.threat_area)
        assert "blasphemous_visions" in g.state.scenario.encounter_discard

    def test_glimpse_the_unspeakable_draws_and_shuffles_into_deck(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        g.state.scenario.vars["tekeli_li_deck"] = ["tekeli_li_b"]
        _resolve(ctrl, "glimpse_the_unspeakable")
        assert inv.damage == 1  # tekeli_li_b 效果
        assert "tekeli_li_b" in inv.deck  # 混洗入牌堆而非放回忒咳哩-哩底
        assert g.state.scenario.vars["tekeli_li_deck"] == []

    def test_glimpse_the_unspeakable_surges_when_empty(self):
        g, ctrl = _mk()
        r = _resolve(ctrl, "glimpse_the_unspeakable")
        assert r.get("surge") is True

    def test_nightmarish_vapors_pending_then_lose_actions(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.actions_remaining = 3
        r = _resolve(ctrl, "nightmarish_vapors")
        assert r["pending"] is True
        assert g.state.scenario.vars["pending_choice"]["investigator_id"] == "player"
        g.state.scenario.vars.pop("pending_choice")
        r = _resolve(ctrl, "nightmarish_vapors", choice="lose_actions")
        assert r["pending"] is False
        assert inv.actions_remaining == 1

    def test_nightmarish_vapors_shuffle_two(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        g.state.scenario.vars["tekeli_li_deck"] = ["tekeli_li_a", "tekeli_li_f"]
        _resolve(ctrl, "nightmarish_vapors", choice="shuffle_2")
        assert sorted(inv.deck) == ["tekeli_li_a", "tekeli_li_f"]
        assert inv.actions_remaining == 3


class TestMiasma:
    def test_miasmatic_torment_surges_without_partner(self):
        g, ctrl = _mk()
        r = _resolve(ctrl, "miasmatic_torment")
        assert r.get("surge") is True

    def test_miasmatic_torment_attach_and_turn_end_damage(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        _register_asset(g, "danforth_c", traits=["ally"], health=3, sanity=2,
                        text="Partner. Uses (5 secrets).")
        asset = _add_asset_instance(g, inv, "a1", "danforth_c")
        r = _resolve(ctrl, "miasmatic_torment")
        assert r.get("surge") is None
        assert asset.exhausted is True
        assert g.state.scenario.vars["miasmatic_torment"]["asset"] == "a1"
        _turn_end(g)
        assert asset.damage == 1

    def test_miasmatic_torment_activate_discard(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        _register_asset(g, "danforth_c", traits=["ally"], health=3,
                        text="Partner. Uses (5 secrets).")
        _add_asset_instance(g, inv, "a1", "danforth_c")
        _resolve(ctrl, "miasmatic_torment")
        _pass_bag(g)  # 智力3 vs 3 → 成功
        assert ee.activate_discard_miasmatic_torment(
            ctrl, "player", skill=Skill.INTELLECT) is True
        assert inv.actions_remaining == 2
        assert "miasmatic_torment" not in g.state.scenario.vars
        assert "miasmatic_torment" in g.state.scenario.encounter_discard

    def test_nebulous_miasma_turn_end_direct_horror(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        _register_asset(g, "ally_b", sanity=2)
        asset = _add_asset_instance(g, inv, "a1", "ally_b")
        _resolve(ctrl, "nebulous_miasma")
        _turn_end(g)
        assert inv.horror == 1  # 直接恐惧
        assert asset.horror == 1
        _round_end(g)
        assert ctrl.location_attachment_instance("test_location", "nebulous_miasma") is None


class TestPenguinsAndSilence:
    def test_wuk_wuk_wuk_pending_then_place_doom(self):
        g, ctrl = _mk()
        e = _add_enemy(g, "p1", "giant_albino_penguin", ["creature"])
        r = _resolve(ctrl, "wuk_wuk_wuk")
        assert r["pending"] is True
        pc = g.state.scenario.vars["pending_choice"]
        assert pc["investigator_id"] == "player"
        r = _resolve(ctrl, "wuk_wuk_wuk", choice="place_doom")
        assert r["pending"] is False
        assert e.doom == 1

    def test_wuk_wuk_wuk_move_to_your_location(self):
        g, ctrl = _mk()
        _add_location(g, "far_loc")
        _add_enemy(g, "p1", "giant_albino_penguin", ["creature"], location="far_loc")
        r = _resolve(ctrl, "wuk_wuk_wuk", choice="move")
        assert r["pending"] is False
        loc = g.state.get_location("test_location")
        far = g.state.get_location("far_loc")
        assert "p1" in loc.enemies and "p1" not in far.enemies

    def test_wuk_wuk_wuk_pulls_from_deck_when_absent(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        g.register_card_data(make_enemy_data(id="giant_albino_penguin"))
        _register_treachery(g, "filler")
        g.state.scenario.encounter_deck = ["filler", "giant_albino_penguin"]
        r = _resolve(ctrl, "wuk_wuk_wuk")
        assert r.get("pending") is False
        spawned = [i for i, inst in g.state.cards_in_play.items()
                   if inst.card_id == "giant_albino_penguin"]
        assert spawned and spawned[0] in inv.threat_area

    def test_polar_mirage_discards_non_weakness_hand_on_clue(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        _register_asset(g, "asset_a")
        wk = CardData(id="weakness_w", name="w", name_cn="w",
                      type=CardType.TREACHERY, subtype="weakness")
        g.register_card_data(wk)
        inv.hand = ["asset_a", "weakness_w"]
        r = _resolve(ctrl, "polar_mirage")
        assert r["message"] == "polar_mirage"
        assert ctrl.location_attachment_instance("test_location", "polar_mirage")
        g.event_bus.emit(EventContext(
            game_state=g.state, event=GameEvent.CLUE_DISCOVERED,
            investigator_id="player", location_id="test_location"))
        assert inv.hand == ["weakness_w"]
        assert "asset_a" in inv.discard
        assert ctrl.location_attachment_instance("test_location", "polar_mirage") is None

    def test_polar_mirage_no_valid_location_discards(self):
        g, ctrl = _mk()
        loc = g.state.get_location("test_location")
        loc.clues = 0
        r = _resolve(ctrl, "polar_mirage")
        assert r["message"] == "polar_mirage"
        assert ctrl.location_attachment_instance("test_location", "polar_mirage") is None
        assert "polar_mirage" in g.state.scenario.encounter_discard

    def test_dark_aurora_frost_plus_fail_horror(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        # 意志3 vs 3，frost=-1 → 失败：2恐惧 + frost 1恐惧
        _frost_bag(g)
        _resolve(ctrl, "dark_aurora")
        assert inv.horror == 3

    def test_dark_aurora_success_only_frost_horror(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.card_data.skills.willpower = 5
        _frost_bag(g)
        _resolve(ctrl, "dark_aurora")
        assert inv.horror == 1


class TestTekeliLi:
    def test_a_horror_and_returns_to_bottom(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        g.state.scenario.vars["tekeli_li_deck"] = ["tekeli_li_g"]
        _resolve(ctrl, "tekeli_li_a")
        assert inv.horror == 1
        assert g.state.scenario.vars["tekeli_li_deck"] == ["tekeli_li_g", "tekeli_li_a"]

    def test_b_damage(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        _resolve(ctrl, "tekeli_li_b")
        assert inv.damage == 1
        assert g.state.scenario.vars["tekeli_li_deck"] == ["tekeli_li_b"]

    def test_c_random_hand_discard(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        _register_asset(g, "x")
        _register_asset(g, "y")
        inv.hand = ["x", "y"]
        _resolve(ctrl, "tekeli_li_c")
        assert len(inv.hand) == 1 and len(inv.discard) == 1

    def test_d_lose_two_resources(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.resources = 5
        _resolve(ctrl, "tekeli_li_d")
        assert inv.resources == 3

    def test_e_lose_action_now(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.actions_remaining = 2
        _resolve(ctrl, "tekeli_li_e")
        assert inv.actions_remaining == 1

    def test_e_lose_action_next_turn(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.actions_remaining = 0
        _resolve(ctrl, "tekeli_li_e")
        assert inv.actions_remaining == 0
        inv.actions_remaining = 3  # 下个回合开始补满
        g.event_bus.emit(EventContext(
            game_state=g.state, event=GameEvent.INVESTIGATOR_TURN_BEGINS,
            investigator_id="player"))
        assert inv.actions_remaining == 2

    def test_f_place_clue_on_location(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        loc = g.state.get_location("test_location")
        inv.clues = 2
        clues0 = loc.clues
        _resolve(ctrl, "tekeli_li_f")
        assert inv.clues == 1
        assert loc.clues == clues0 + 1

    def test_g_discard_an_asset(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        _register_asset(g, "coat")
        _add_asset_instance(g, inv, "a1", "coat")
        _resolve(ctrl, "tekeli_li_g")
        assert "a1" not in inv.play_area


class TestCoverage:
    def test_all_eoe_treacheries_handled(self):
        """edge_of_the_earth.json 中全部40张诡计都由本模块处理（无核心重印）。"""
        import json
        from pathlib import Path
        data = json.loads((Path(__file__).resolve().parents[2]
                           / "data/encounter_cards/edge_of_the_earth.json").read_text())
        ids = [c["id"] for c in data["cards"] if c.get("type") == "treachery"]
        assert len(ids) == 40
        for cid in ids:
            g, ctrl = _mk()
            g.state.scenario.vars.pop("pending_choice", None)
            log = ctrl.action_log
            log.clear()
            r = _resolve(ctrl, cid)
            assert r is not None, cid
            assert not any("(未实现)" in m for m in log), cid
