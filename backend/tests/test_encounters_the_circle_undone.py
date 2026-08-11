"""Tests for The Circle Undone encounter treachery effects."""

from __future__ import annotations

from backend.engine.event_bus import EventContext
from backend.models.enums import CardType, ChaosTokenType, GameEvent, PlayerClass
from backend.models.state import CardData, CardInstance
from backend.scenarios import encounters_the_circle_undone as tcu
from backend.tests.conftest import make_asset_data, make_enemy_data, make_location_data
from backend.tests.test_scenario_tokens import _add_enemy, _make_game


def _mk(scenario_id="the_witching_hour"):
    return _make_game(scenario_id)


def _fail_bag(g):
    """Force the next skill test to fail."""
    g.chaos_bag.tokens = [ChaosTokenType.AUTO_FAIL]


def _pass_bag(g):
    g.chaos_bag.tokens = [ChaosTokenType.ZERO]


def _register_treachery(g, card_id, traits=None):
    g.register_card_data(CardData(id=card_id, name=card_id, name_cn=card_id,
                                  type=CardType.TREACHERY, traits=traits or []))


def _register_enemy(g, card_id, keywords=None):
    g.register_card_data(make_enemy_data(id=card_id, keywords=keywords or []))


def _add_location(g, location_id, clues=0):
    data = make_location_data(id=location_id)
    g.register_card_data(data)
    g.add_location(location_id, data, clues=clues)


def _add_asset(g, inv, instance_id, card_id, traits=None, health=None):
    cd = make_asset_data(id=card_id, traits=traits or [], health=health)
    g.register_card_data(cd)
    inst = CardInstance(instance_id=instance_id, card_id=card_id,
                        owner_id="player", controller_id="player")
    g.state.cards_in_play[instance_id] = inst
    inv.play_area.append(instance_id)
    return inst


def _place_threat(g, inv, instance_id, card_id):
    inst = CardInstance(instance_id=instance_id, card_id=card_id,
                        owner_id="player", controller_id="player")
    g.state.cards_in_play[instance_id] = inst
    inv.threat_area.append(instance_id)
    return inst


def _resolve(ctrl, card_id, choice=None):
    return tcu.resolve_treachery(ctrl, card_id, investigator_id="player",
                                 choice=choice)


class TestWitchingHour:
    def test_watchers_grasp_heals_readies_engages_attacks(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        w = _add_enemy(g, "w1", "the_spectral_watcher", ["ancient one", "elite"])
        w.damage = 3
        w.exhausted = True
        r = _resolve(ctrl, "watchers_grasp")
        assert r["message"] == "watchers_grasp"
        assert w.damage == 0 and w.exhausted is False
        assert "w1" in inv.threat_area
        assert inv.damage == 1 and inv.horror == 1  # 立即攻击（默认1伤1恐）

    def test_watchers_grasp_no_watcher_noop(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        r = _resolve(ctrl, "watchers_grasp")
        assert r["message"] == "watchers_grasp"
        assert inv.damage == 0 and inv.horror == 0

    def test_daemonic_piping_surge_and_counts(self):
        g, ctrl = _mk()
        r = _resolve(ctrl, "daemonic_piping")
        assert r.get("surge") is True
        assert g.state.scenario.vars["daemonic_piping"] == 1

    def test_daemonic_piping_third_copy_spawns_piper(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        _register_enemy(g, "piper_of_azathoth", ["monster", "elite"])
        g.state.scenario.vars["daemonic_piping"] = 2
        r = _resolve(ctrl, "daemonic_piping")
        assert r.get("surge") is True
        assert g.state.scenario.vars["daemonic_piping"] == 0
        spawned = [i for i, inst in g.state.cards_in_play.items()
                   if inst.card_id == "piper_of_azathoth"]
        assert spawned and spawned[0] in inv.threat_area

    def test_daemonic_piping_piper_in_play_horror(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        _add_enemy(g, "p1", "piper_of_azathoth", ["monster", "elite"])
        r = _resolve(ctrl, "daemonic_piping")
        assert r.get("surge") is True
        assert inv.horror == 1  # 同地点（无连接地点）


class TestAtDeathsDoorstep:
    def test_diabolic_voices_discard_then_horror(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.card_data.skills.willpower = 1
        inv.hand = ["a", "b"]
        _fail_bag(g)  # AUTO_FAIL：margin = 难度3
        _resolve(ctrl, "diabolic_voices")
        assert inv.hand == []
        assert len(inv.discard) == 2
        assert inv.horror == 1  # 无法弃的第3张 → 1恐惧

    def test_diabolic_voices_difficulty_scales_with_discard(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.card_data.skills.willpower = 1
        inv.hand = ["a", "b"]
        g.state.scenario.encounter_discard = ["diabolic_voices"] * 2
        _fail_bag(g)  # 难度 3+2=5，margin 5
        _resolve(ctrl, "diabolic_voices")
        assert len(inv.discard) == 2
        assert inv.horror == 3

    def test_wracked_enters_threat_and_activate_discards(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.card_data.skills.willpower = 10
        inv.actions_remaining = 3
        _resolve(ctrl, "wracked")
        assert any(g.state.cards_in_play[i].card_id == "wracked"
                   for i in inv.threat_area)
        assert g.state.scenario.vars["wracked"]["player"] is True
        _pass_bag(g)
        assert tcu.activate_discard_hex(ctrl, "player", "wracked") is True
        assert inv.actions_remaining == 2
        assert "wracked" in g.state.scenario.encounter_discard
        assert not any(i in g.state.cards_in_play
                       and g.state.cards_in_play[i].card_id == "wracked"
                       for i in inv.threat_area)

    def test_hex_auto_success_with_exhausted_witch(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.actions_remaining = 3
        e = _add_enemy(g, "e1", "witch_enemy", ["witch"])
        e.exhausted = True
        _resolve(ctrl, "bedeviled")
        _fail_bag(g)  # 自动成功，袋内容无关
        assert tcu.activate_discard_hex(ctrl, "player", "bedeviled") is True
        assert "bedeviled" in g.state.scenario.encounter_discard

    def test_bedeviled_enters_threat_with_restriction_record(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        _resolve(ctrl, "bedeviled")
        assert any(g.state.cards_in_play[i].card_id == "bedeviled"
                   for i in inv.threat_area)
        assert g.state.scenario.vars["bedeviled"]["player"] is True

    def test_mysteries_of_the_lodge_doom_on_nearest_cultist(self):
        g, ctrl = _mk()
        e = _add_enemy(g, "e1", "lodge_neophyte", ["cultist"])
        r = _resolve(ctrl, "mysteries_of_the_lodge")
        assert r.get("surge") is None
        assert e.doom == 1
        assert g.state.scenario.vars["mysteries_of_the_lodge"]["target"] == "e1"

    def test_mysteries_of_the_lodge_surges_without_cultist(self):
        g, ctrl = _mk()
        r = _resolve(ctrl, "mysteries_of_the_lodge")
        assert r.get("surge") is True

    def test_evil_past_second_copy_surges(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        _resolve(ctrl, "evil_past")
        assert any(g.state.cards_in_play[i].card_id == "evil_past"
                   for i in inv.threat_area)
        r = _resolve(ctrl, "evil_past")
        assert r.get("surge") is True

    def test_evil_past_deck_empty_trigger(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.card_data.skills.willpower = 10
        _resolve(ctrl, "evil_past")
        _fail_bag(g)  # notify 内先造成2恐惧（不经检定）
        tcu.notify_encounter_deck_empty(ctrl)
        assert inv.horror == 2
        # 意志10 vs 3（AUTO_FAIL 已消耗？不——AUTO_FAIL 每抽必中；重设成功袋）
        _pass_bag(g)
        tcu.notify_encounter_deck_empty(ctrl)
        assert inv.horror == 4  # 第二次仍受2恐惧
        assert not any(i in g.state.cards_in_play
                       and g.state.cards_in_play[i].card_id == "evil_past"
                       for i in inv.threat_area)

    def test_centuries_of_secrets_curse_direct_damage(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.card_data.skills.willpower = 1
        _register_treachery(g, "curse_t", traits=["curse"])
        for c in ("f1", "f2", "f3", "f4"):
            _register_treachery(g, c)
        g.state.scenario.encounter_deck = ["curse_t", "f1", "f2", "f3", "f4"]
        ally = _add_asset(g, inv, "al1", "ally_a", traits=["ally"], health=2)
        _fail_bag(g)  # margin 5 → 弃5张，含诅咒诡计
        _resolve(ctrl, "centuries_of_secrets")
        assert sorted(g.state.scenario.encounter_discard) == \
            ["curse_t", "f1", "f2", "f3", "f4"]
        assert inv.damage == 1
        assert ally.damage == 1

    def test_centuries_of_secrets_no_curse_no_damage(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.card_data.skills.willpower = 1
        _register_treachery(g, "f1")
        g.state.scenario.encounter_deck = ["f1"]
        _fail_bag(g)
        _resolve(ctrl, "centuries_of_secrets")
        assert inv.damage == 0

    def test_whispers_in_the_dark_haunted_and_round_end(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        _resolve(ctrl, "whispers_in_the_dark")
        assert g.state.scenario.vars["whispers_in_the_dark"] is True
        # 生效期间：任意地点闹鬼 = 受1恐惧（借雾中身形结算）
        r = _resolve(ctrl, "shapes_in_the_mist")
        assert r.get("surge") is True
        assert inv.horror == 1
        g.event_bus.emit(EventContext(game_state=g.state, event=GameEvent.ROUND_ENDS))
        assert "whispers_in_the_dark" not in g.state.scenario.vars
        assert "whispers_in_the_dark" in g.state.scenario.encounter_discard

    def test_trapped_spirits_damage_per_point(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.card_data.skills.agility = 1
        _fail_bag(g)  # margin = 难度3
        _resolve(ctrl, "trapped_spirits")
        assert inv.damage == 3

    def test_realm_of_torment_turn_begin_haunted_turn_end_discard(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.card_data.skills.willpower = 10
        g.state.scenario.vars["haunted"] = {
            "test_location": [{"type": "horror", "amount": 2}]}
        _resolve(ctrl, "realm_of_torment")
        assert any(g.state.cards_in_play[i].card_id == "realm_of_torment"
                   for i in inv.threat_area)
        g.event_bus.emit(EventContext(
            game_state=g.state, event=GameEvent.INVESTIGATOR_TURN_BEGINS,
            investigator_id="player"))
        assert inv.horror == 2
        _pass_bag(g)
        g.event_bus.emit(EventContext(
            game_state=g.state, event=GameEvent.INVESTIGATOR_TURN_ENDS,
            investigator_id="player"))
        assert "realm_of_torment" in g.state.scenario.encounter_discard

    def test_shapes_in_the_mist_surge_and_haunted(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        g.state.scenario.vars["haunted"] = {
            "test_location": [{"type": "damage", "amount": 2}]}
        r = _resolve(ctrl, "shapes_in_the_mist")
        assert r.get("surge") is True
        assert inv.damage == 2

    def test_terror_in_the_night_fail_by_3_surges(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.card_data.skills.willpower = 1
        _fail_bag(g)  # margin 4 ≥ 3
        r = _resolve(ctrl, "terror_in_the_night")
        assert r.get("surge") is True
        assert g.state.scenario.vars["terror_in_the_night"] == 1

    def test_terror_in_the_night_three_copies_horror_all(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.card_data.skills.willpower = 1
        g.state.scenario.vars["terror_in_the_night"] = 2
        _fail_bag(g)
        _resolve(ctrl, "terror_in_the_night")
        assert inv.horror == 3
        assert g.state.scenario.vars["terror_in_the_night"] == 0

    def test_fate_of_all_fools_no_other_copy_enters_threat(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        r = _resolve(ctrl, "fate_of_all_fools")
        assert r["pending"] is False
        assert any(g.state.cards_in_play[i].card_id == "fate_of_all_fools"
                   for i in inv.threat_area)

    def test_fate_of_all_fools_pending_and_place_doom(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        other = _place_threat(g, inv, "ff1", "fate_of_all_fools")
        r = _resolve(ctrl, "fate_of_all_fools")
        assert r["pending"] is True
        assert g.state.scenario.vars["pending_choice"]["investigator_id"] == "player"
        g.state.scenario.vars.pop("pending_choice")
        r = _resolve(ctrl, "fate_of_all_fools", choice="place_doom")
        assert r["pending"] is False
        assert other.doom == 1

    def test_fate_of_all_fools_take_direct_damage(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        _place_threat(g, inv, "ff1", "fate_of_all_fools")
        r = _resolve(ctrl, "fate_of_all_fools", choice="take_direct")
        assert r["pending"] is False
        assert inv.damage == 2


class TestSecretName:
    def test_meddlesome_familiar_spawns_brown_jenkin(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        _register_enemy(g, "brown_jenkin", ["creature", "elite"])
        g.state.scenario.encounter_deck = ["brown_jenkin"]
        _resolve(ctrl, "meddlesome_familiar")
        loc = g.state.get_location("test_location")
        spawned = [i for i in loc.enemies
                   if g.state.cards_in_play[i].card_id == "brown_jenkin"]
        assert spawned
        assert inv.damage == 1
        assert g.state.scenario.encounter_deck == []

    def test_meddlesome_familiar_jenkin_in_play_spawns_rats_engaged(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        _add_enemy(g, "bj", "brown_jenkin", ["creature", "elite"])
        _register_enemy(g, "swarm_of_rats", ["creature"])
        g.state.scenario.encounter_discard = ["swarm_of_rats"]
        _resolve(ctrl, "meddlesome_familiar")
        spawned = [i for i, inst in g.state.cards_in_play.items()
                   if inst.card_id == "swarm_of_rats"]
        assert spawned and spawned[0] in inv.threat_area
        assert inv.damage == 1

    def test_ghostly_presence_fetches_nahab(self):
        g, ctrl = _mk()
        _register_enemy(g, "nahab", ["monster", "geist", "elite"])
        g.state.scenario.encounter_deck = ["nahab"]
        _resolve(ctrl, "ghostly_presence")
        loc = g.state.get_location("test_location")
        assert any(g.state.cards_in_play[i].card_id == "nahab" for i in loc.enemies)

    def test_ghostly_presence_nahab_in_play_attacks(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        n = _add_enemy(g, "n1", "nahab", ["monster", "geist", "elite"])
        n.exhausted = True
        _resolve(ctrl, "ghostly_presence")
        assert n.exhausted is False
        assert inv.damage == 1 and inv.horror == 1

    def test_extradimensional_visions_discards_asset(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.card_data.skills.willpower = 1
        _add_asset(g, inv, "a1", "asset_a")
        _fail_bag(g)
        _resolve(ctrl, "extradimensional_visions")
        assert "a1" not in inv.play_area
        assert "asset_a" in inv.discard

    def test_extradimensional_visions_difficulty_scales(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.card_data.skills.willpower = 1
        g.state.scenario.encounter_discard = ["x"] * 10
        _fail_bag(g)
        _resolve(ctrl, "extradimensional_visions")
        assert any("意志3" in m for m in ctrl.action_log)

    def test_pulled_by_the_stars_no_move_horror(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        _resolve(ctrl, "pulled_by_the_stars")
        g.event_bus.emit(EventContext(
            game_state=g.state, event=GameEvent.INVESTIGATOR_TURN_ENDS,
            investigator_id="player"))
        assert inv.horror == 2
        # 移动过的回合不受恐惧
        g.event_bus.emit(EventContext(
            game_state=g.state, event=GameEvent.MOVE_ACTION_INITIATED,
            investigator_id="player", location_id="elsewhere"))
        g.event_bus.emit(EventContext(
            game_state=g.state, event=GameEvent.INVESTIGATOR_TURN_ENDS,
            investigator_id="player"))
        assert inv.horror == 2

    def test_disquieting_dreams_full_cycle(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.card_data.skills.willpower = 1
        _register_treachery(g, "x1")
        g.state.scenario.encounter_deck = ["x1"]
        _fail_bag(g)
        _resolve(ctrl, "disquieting_dreams")
        assert any(g.state.cards_in_play[i].card_id == "disquieting_dreams"
                   for i in inv.threat_area)
        # 回合结束：弃遭遇堆顶
        g.event_bus.emit(EventContext(
            game_state=g.state, event=GameEvent.INVESTIGATOR_TURN_ENDS,
            investigator_id="player"))
        assert "x1" in g.state.scenario.encounter_discard
        # 遭遇牌堆耗尽：弃掉不安的梦，翻牌堆顶10张，抽弱点弃其余
        g.register_card_data(CardData(
            id="wk", name="wk", name_cn="wk", type=CardType.TREACHERY,
            card_class=PlayerClass.NEUTRAL, subtype="weakness"))
        _register_treachery(g, "c1")
        _register_treachery(g, "c2")
        inv.deck = ["wk", "c1", "c2"]
        tcu.notify_encounter_deck_empty(ctrl)
        assert "disquieting_dreams" in g.state.scenario.encounter_discard
        assert inv.hand == ["wk"]
        assert inv.discard == ["c1", "c2"]


class TestWagesOfSin:
    def test_punishment_damage_on_enemy_defeated(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        _resolve(ctrl, "punishment")
        g.event_bus.emit(EventContext(
            game_state=g.state, event=GameEvent.ENEMY_DEFEATED))
        assert inv.damage == 1
        # 弃掉后不再触发
        inv.actions_remaining = 3
        inv.card_data.skills.willpower = 10
        _pass_bag(g)
        assert tcu.activate_discard_hex(ctrl, "player", "punishment") is True
        g.event_bus.emit(EventContext(
            game_state=g.state, event=GameEvent.ENEMY_DEFEATED))
        assert inv.damage == 1

    def test_burdens_of_the_past_surges_without_unfinished_business(self):
        g, ctrl = _mk()
        r = _resolve(ctrl, "burdens_of_the_past")
        assert r.get("surge") is True

    def test_burdens_of_the_past_triggers_unfinished_business(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        _place_threat(g, inv, "ub1", "unfinished_business_a")
        r = _resolve(ctrl, "burdens_of_the_past")
        assert r.get("surge") is None
        assert g.state.scenario.vars["unfinished_business_triggered"] == 1

    def test_ominous_portents_test_branch(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.card_data.skills.willpower = 1
        _fail_bag(g)
        _resolve(ctrl, "ominous_portents")
        assert inv.horror == 2

    def test_ominous_portents_draw_spectral(self):
        g, ctrl = _mk()
        g.state.scenario.vars["spectral_encounter_deck"] = ["ancient_evils"]
        doom0 = g.state.scenario.doom_on_agenda
        r = _resolve(ctrl, "ominous_portents")
        assert r["pending"] is True
        g.state.scenario.vars.pop("pending_choice")
        r = _resolve(ctrl, "ominous_portents", choice="draw_spectral")
        assert r["pending"] is False
        assert g.state.scenario.vars["spectral_encounter_deck"] == []
        assert g.state.scenario.doom_on_agenda == doom0 + 1  # 核心分支结算远古邪恶

    def test_grave_light_from_standard_shuffles_into_spectral(self):
        g, ctrl = _mk()
        r = _resolve(ctrl, "grave_light")
        assert r.get("surge") is True
        assert "grave_light" in g.state.scenario.vars["spectral_encounter_deck"]

    def test_grave_light_from_spectral_takes_damage(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        g.state.scenario.vars["drawing_from_spectral"] = True
        _resolve(ctrl, "grave_light")
        assert inv.damage == 2
        assert "grave_light" in g.state.scenario.encounter_discard

    def test_bane_of_the_living_geist_branch(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        _register_treachery(g, "t1")
        _register_enemy(g, "geist_e", ["geist"])
        g.state.scenario.vars["spectral_encounter_deck"] = ["t1", "geist_e"]
        _resolve(ctrl, "bane_of_the_living")
        spawned = [i for i, inst in g.state.cards_in_play.items()
                   if inst.card_id == "geist_e"]
        assert spawned and spawned[0] in inv.threat_area
        assert g.state.scenario.vars["spectral_encounter_discard"] == ["t1"]

    def test_bane_of_the_living_pending_and_flip(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        _place_threat(g, inv, "ub1", "unfinished_business_a")
        _register_enemy(g, "geist_e", ["geist"])
        g.state.scenario.vars["spectral_encounter_deck"] = ["geist_e"]
        r = _resolve(ctrl, "bane_of_the_living")
        assert r["pending"] is True
        g.state.scenario.vars.pop("pending_choice")
        r = _resolve(ctrl, "bane_of_the_living", choice="flip")
        assert r["pending"] is False
        assert g.state.scenario.vars["unfinished_business_flipped"] == 1


class TestUnionAndDisillusion:
    def test_call_to_order_spawns_cultists_at_empty_location(self):
        g, ctrl = _mk()
        _register_enemy(g, "cult_a", ["cultist"])
        _register_enemy(g, "cult_b", ["cultist"])
        g.state.scenario.encounter_discard = ["cult_a", "cult_b"]
        _add_location(g, "loc2", clues=5)
        r = _resolve(ctrl, "call_to_order")
        assert r.get("surge") is None
        loc2 = g.state.get_location("loc2")
        spawned = sorted(g.state.cards_in_play[i].card_id for i in loc2.enemies)
        assert spawned == ["cult_a", "cult_b"]
        assert g.state.scenario.encounter_discard == []

    def test_call_to_order_surges_without_cultists(self):
        g, ctrl = _mk()
        _add_location(g, "loc2", clues=5)
        r = _resolve(ctrl, "call_to_order")
        assert r.get("surge") is True

    def test_expulsion_engages_attacks_and_takes_keys(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        e = _add_enemy(g, "e1", "lodge_neophyte", ["cultist"])
        e.exhausted = True
        g.state.scenario.vars["keys"] = {"player": ["skull", "cultist", "other"]}
        r = _resolve(ctrl, "expulsion")
        assert r.get("surge") is None
        assert e.exhausted is False
        assert "e1" in inv.threat_area
        assert inv.damage == 1 and inv.horror == 1
        assert g.state.scenario.vars["enemy_keys"]["e1"] == ["skull", "cultist"]
        assert g.state.scenario.vars["keys"]["player"] == ["other"]

    def test_expulsion_surges_without_cultist(self):
        g, ctrl = _mk()
        r = _resolve(ctrl, "expulsion")
        assert r.get("surge") is True

    def test_beneath_the_lodge_lose_clues_then_horror(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.card_data.skills.intellect = 1
        inv.clues = 2
        _fail_bag(g)  # margin = 难度3
        _resolve(ctrl, "beneath_the_lodge")
        assert inv.clues == 0
        assert inv.horror == 1

    def test_beneath_the_lodge_key_raises_difficulty(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.card_data.skills.intellect = 1
        g.state.scenario.vars["keys"] = {"player": ["skull"]}
        _fail_bag(g)
        _resolve(ctrl, "beneath_the_lodge")
        assert any("智力4" in m for m in ctrl.action_log)

    def test_mark_of_the_order_per_key_penalties(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.hand = ["h1", "h2"]
        inv.resources = 5
        g.state.scenario.vars["keys"] = {
            "player": ["skull", "cultist", "tablet", "elder_thing"]}
        r = _resolve(ctrl, "mark_of_the_order")
        assert r.get("surge") is True
        assert inv.damage == 1 and inv.horror == 1
        assert inv.hand == [] and len(inv.discard) == 2
        assert inv.resources == 2


class TestInTheClutchesOfChaos:
    def test_death_approaches_enters_threat_and_surges(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        r = _resolve(ctrl, "death_approaches")
        assert r.get("surge") is True
        assert any(g.state.cards_in_play[i].card_id == "death_approaches"
                   for i in inv.threat_area)

    def test_marked_for_death_difficulty_scales_with_horror(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.card_data.skills.agility = 1
        inv.horror = 2
        _fail_bag(g)
        _resolve(ctrl, "marked_for_death")
        assert any("敏捷4" in m for m in ctrl.action_log)
        assert inv.damage == 2

    def test_watchers_gaze_failed_investigators_resolve_haunted(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.card_data.skills.willpower = 1
        g.state.scenario.vars["haunted"] = {
            "test_location": [{"type": "horror", "amount": 1}]}
        _fail_bag(g)
        _resolve(ctrl, "watchers_gaze")
        assert inv.horror == 1

    def test_chaos_manifest_places_breaches_on_random_locations(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.card_data.skills.willpower = 1
        _add_location(g, "loc2")
        _add_location(g, "loc3")
        _fail_bag(g)  # margin = 难度3 → 3个不同地点各+1裂口
        _resolve(ctrl, "chaos_manifest")
        breaches = g.state.scenario.vars["breaches"]
        assert sum(breaches.values()) == 3
        assert len(breaches) == 3

    def test_primordial_gateway_attach_breaches_and_close(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.card_data.skills.intellect = 10
        inv.actions_remaining = 3
        _resolve(ctrl, "primordial_gateway")
        assert ctrl.location_attachment_instance("test_location",
                                                 "primordial_gateway")
        assert g.state.scenario.vars["breaches"]["test_location"] == 3
        _pass_bag(g)
        assert tcu.activate_close_gateway(ctrl, "player") is True
        assert inv.actions_remaining == 2
        assert ctrl.location_attachment_instance("test_location",
                                                 "primordial_gateway") is None
        assert "primordial_gateway" in g.state.scenario.encounter_discard

    def test_terror_unleashed_places_breach_and_horror(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        _resolve(ctrl, "terror_unleashed")
        assert g.state.scenario.vars["breaches"]["test_location"] == 1
        assert inv.horror == 1  # X = 0毁灭 + 1裂口

    def test_terror_unleashed_counts_doom_and_breaches(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        g.state.scenario.vars["breaches"] = {"test_location": 2}
        g.state.get_location("test_location").doom = 1
        _resolve(ctrl, "terror_unleashed")
        assert inv.horror == 3  # X = 1毁灭 + 2裂口

    def test_secrets_of_the_beyond_breaches_per_doom(self):
        g, ctrl = _mk()
        e = _add_enemy(g, "e1", "keeper_of_secrets", ["cultist"])
        e.doom = 2
        r = _resolve(ctrl, "secrets_of_the_beyond")
        assert r.get("surge") is None
        assert g.state.scenario.vars["breaches"]["test_location"] == 2

    def test_secrets_of_the_beyond_surges_without_doom(self):
        g, ctrl = _mk()
        _add_enemy(g, "e1", "keeper_of_secrets", ["cultist"])
        r = _resolve(ctrl, "secrets_of_the_beyond")
        assert r.get("surge") is True

    def test_toil_and_trouble_incursion_default(self):
        g, ctrl = _mk()
        _resolve(ctrl, "toil_and_trouble")
        assert g.state.scenario.vars["incursions"]["test_location"] == 1

    def test_toil_and_trouble_resolves_power_treachery(self):
        g, ctrl = _mk()
        _register_treachery(g, "ancient_evils", traits=["power"])
        g.state.scenario.encounter_discard = ["ancient_evils"]
        doom0 = g.state.scenario.doom_on_agenda
        r = _resolve(ctrl, "toil_and_trouble")
        assert r["pending"] is True
        g.state.scenario.vars.pop("pending_choice")
        r = _resolve(ctrl, "toil_and_trouble", choice="resolve_power")
        assert r["pending"] is False
        assert g.state.scenario.doom_on_agenda == doom0 + 1


class TestBeforeTheBlackThrone:
    def test_ultimate_chaos_attach_damage_and_surge(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.card_data.skills.willpower = 1
        _add_enemy(g, "az", "azathoth", ["ancient one", "elite"])
        _fail_bag(g)  # margin 4：≥2 受1伤1恐，≥3 涌动
        r = _resolve(ctrl, "ultimate_chaos")
        assert r.get("surge") is True
        assert inv.damage == 1 and inv.horror == 1
        assert len(g.state.scenario.vars["ultimate_chaos_attached"]) == 1

    def test_ultimate_chaos_three_copies_doom_on_azathoth(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.card_data.skills.willpower = 1
        az = _add_enemy(g, "az", "azathoth", ["ancient one", "elite"])
        for _ in range(3):
            _fail_bag(g)
            _resolve(ctrl, "ultimate_chaos")
        assert g.state.scenario.vars["ultimate_chaos_attached"] == []
        assert az.doom == 1
        assert g.state.scenario.encounter_discard.count("ultimate_chaos") == 3

    def test_whispered_bargain_pending_and_attack(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        _add_enemy(g, "az", "azathoth", ["ancient one", "elite"])
        r = _resolve(ctrl, "whispered_bargain")
        assert r["pending"] is True
        assert g.state.scenario.vars["pending_choice"]["investigator_id"] == "player"
        g.state.scenario.vars.pop("pending_choice")
        r = _resolve(ctrl, "whispered_bargain", choice="attack")
        assert r["pending"] is False
        assert inv.damage == 1 and inv.horror == 1

    def test_whispered_bargain_place_doom(self):
        g, ctrl = _mk()
        az = _add_enemy(g, "az", "azathoth", ["ancient one", "elite"])
        r = _resolve(ctrl, "whispered_bargain", choice="place_doom")
        assert r["pending"] is False
        assert az.doom == 1

    def test_whispered_bargain_no_azathoth_noop(self):
        g, ctrl = _mk()
        r = _resolve(ctrl, "whispered_bargain")
        assert r["pending"] is False
        assert "pending_choice" not in g.state.scenario.vars

    def test_the_end_is_nigh_moves_cultist_doom(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.card_data.skills.willpower = 1
        az = _add_enemy(g, "az", "azathoth", ["ancient one", "elite"])
        e = _add_enemy(g, "e1", "cultist_a", ["cultist"])
        e.doom = 2
        _fail_bag(g)  # 无密谋 → 难度 1+4=5
        _resolve(ctrl, "the_end_is_nigh")
        assert e.doom == 0
        assert az.doom == 2

    def test_the_end_is_nigh_no_cultists_places_one(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.card_data.skills.willpower = 1
        az = _add_enemy(g, "az", "azathoth", ["ancient one", "elite"])
        _fail_bag(g)
        _resolve(ctrl, "the_end_is_nigh")
        assert az.doom == 1

    def test_a_world_in_darkness_surges_without_doom(self):
        g, ctrl = _mk()
        _add_enemy(g, "az", "azathoth", ["ancient one", "elite"])
        r = _resolve(ctrl, "a_world_in_darkness")
        assert r.get("surge") is True

    def test_a_world_in_darkness_auto_resource_then_discard(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        az = _add_enemy(g, "az", "azathoth", ["ancient one", "elite"])
        az.doom = 2
        inv.resources = 1
        inv.hand = ["c1"]
        _resolve(ctrl, "a_world_in_darkness")
        assert inv.resources == 0
        assert inv.hand == [] and inv.discard == ["c1"]


class TestCoverage:
    def test_all_tcu_treacheries_handled_except_dunwich_reprints(self):
        """the_circle_undone.json 中全部42张诡计：40张由本模块处理；
        eager_for_death / psychopomps_song 为 dunwich 既有 id，由 dunwich
        分支处理，本模块返回 None。"""
        import json
        from pathlib import Path
        data = json.loads((Path(__file__).resolve().parents[2]
                           / "data/encounter_cards/the_circle_undone.json").read_text())
        ids = [c["id"] for c in data["cards"] if c.get("type") == "treachery"]
        assert len(ids) == 42
        skipped = {"eager_for_death", "psychopomps_song"}
        for cid in ids:
            g, ctrl = _mk()
            g.state.scenario.vars.pop("pending_choice", None)
            log = ctrl.action_log
            log.clear()
            r = _resolve(ctrl, cid)
            if cid in skipped:
                assert r is None, cid
                continue
            assert r is not None, cid
            assert not any("(未实现)" in m for m in log), cid
