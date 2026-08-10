"""Tests for Path to Carcosa encounter treachery effects."""

from __future__ import annotations

from backend.engine.event_bus import EventContext
from backend.models.enums import CardType, ChaosTokenType, GameEvent, SlotType
from backend.models.state import CardData, CardInstance
from backend.scenarios import carcosa_encounters as ce
from backend.tests.conftest import make_asset_data, make_enemy_data
from backend.tests.test_scenario_tokens import _add_enemy, _make_game


def _mk(scenario_id="the_last_king"):
    return _make_game(scenario_id)


def _fail_bag(g):
    """Force the next skill test to fail."""
    g.chaos_bag.tokens = [ChaosTokenType.AUTO_FAIL]


def _pass_bag(g):
    g.chaos_bag.tokens = [ChaosTokenType.ZERO]


def _register_treachery(g, card_id, traits=None):
    g.register_card_data(CardData(id=card_id, name=card_id, name_cn=card_id,
                                  type=CardType.TREACHERY, traits=traits or []))


def _register_asset(g, card_id, cost=0, traits=None):
    cd = make_asset_data(id=card_id, cost=cost)
    cd.traits = traits or []
    g.register_card_data(cd)
    return cd


def _add_asset_instance(g, inv, instance_id, card_id, slots=None):
    inst = CardInstance(instance_id=instance_id, card_id=card_id,
                        owner_id="player", controller_id="player",
                        slot_used=list(slots or []))
    g.state.cards_in_play[instance_id] = inst
    inv.play_area.append(instance_id)
    return inst


class TestTheLastKingTreacheries:
    def test_fine_dining_pending_then_place_clue(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        _register_asset(g, "constance_dumaine_b", traits=["bystander"])
        inst = CardInstance(instance_id="by1", card_id="constance_dumaine_b",
                            owner_id="scenario", controller_id="scenario")
        g.state.cards_in_play["by1"] = inst
        inv.clues = 2

        r = ctrl.resolve_encounter_card("fine_dining")
        assert r["pending"] is True
        pc = g.state.scenario.vars["pending_choice"]
        assert pc["investigator_id"] == "player"
        g.state.scenario.vars.pop("pending_choice")

        r = ctrl.resolve_encounter_card("fine_dining", choice="place_clue")
        assert r["pending"] is False
        assert inv.clues == 1
        assert inst.uses.get("clues") == 1

    def test_fine_dining_no_bystander_takes_damage(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.clues = 2
        r = ctrl.resolve_encounter_card("fine_dining")
        assert r["pending"] is False
        assert inv.damage == 1 and inv.horror == 1

    def test_tough_crowd_flag_cleared_at_round_end(self):
        g, ctrl = _mk()
        ctrl.resolve_encounter_card("tough_crowd")
        assert g.state.scenario.vars.get("tough_crowd") is True
        g.event_bus.emit(EventContext(game_state=g.state, event=GameEvent.ROUND_ENDS))
        assert "tough_crowd" not in g.state.scenario.vars


class TestWhispersInYourHead:
    def test_each_copy_enters_hand_with_restriction_marker(self):
        for cid in ("whispers_in_your_head_a", "whispers_in_your_head_b",
                    "whispers_in_your_head_c", "whispers_in_your_head_d"):
            g, ctrl = _mk()
            inv = g.state.get_investigator("player")
            r = ctrl.resolve_encounter_card(cid)
            assert r["message"] == cid
            assert cid in inv.hand
            assert g.state.scenario.vars["whispers_in_your_head"]["player"] == cid

    def test_activate_discard_costs_two_actions(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.actions_remaining = 3
        ctrl.resolve_encounter_card("whispers_in_your_head_d")
        assert ce.activate_discard_whispers(ctrl, "player") is True
        assert inv.actions_remaining == 1
        assert "whispers_in_your_head_d" not in inv.hand
        assert "whispers_in_your_head_d" in inv.discard
        assert "player" not in g.state.scenario.vars["whispers_in_your_head"]

    def test_activate_discard_requires_two_actions(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.actions_remaining = 1
        ctrl.resolve_encounter_card("whispers_in_your_head_a")
        assert ce.activate_discard_whispers(ctrl, "player") is False
        assert "whispers_in_your_head_a" in inv.hand


class TestDelusionsAndByakhee:
    def test_descent_into_madness_loses_action_and_surges(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.horror = 3
        inv.actions_remaining = 3
        r = ctrl.resolve_encounter_card("descent_into_madness")
        assert r.get("surge") is True
        assert inv.actions_remaining == 2

    def test_descent_into_madness_below_threshold_keeps_actions(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.horror = 2
        inv.actions_remaining = 3
        r = ctrl.resolve_encounter_card("descent_into_madness")
        assert r.get("surge") is True
        assert inv.actions_remaining == 3

    def test_hunted_by_byakhee_draws_byakhee_and_omen_horror(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.card_data.skills.agility = 1
        g.register_card_data(make_enemy_data(id="swift_byakhee", keywords=["byakhee"]))
        _register_treachery(g, "black_stars_rise_a", traits=["omen"])
        _register_treachery(g, "filler")
        g.state.scenario.encounter_deck = ["swift_byakhee", "black_stars_rise_a", "filler"]

        _fail_bag(g)  # 敏捷1 vs 难度6 → margin 5 → 翻开全部3张
        r = ctrl.resolve_encounter_card("hunted_by_byakhee")
        assert r["message"] == "hunted_by_byakhee"
        # 拜亚基敌人被抽到并交战
        spawned = [i for i, inst in g.state.cards_in_play.items()
                   if inst.card_id == "swift_byakhee"]
        assert spawned and spawned[0] in inv.threat_area
        # 翻开征兆诡计 → 1恐惧
        assert inv.horror == 1
        # 未抽取的卡洗回遭遇牌堆
        assert sorted(g.state.scenario.encounter_deck) == ["black_stars_rise_a", "filler"]


class TestEvilPortents:
    def test_black_stars_rise_fail_takes_horror_per_point(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.card_data.skills.intellect = 1
        _fail_bag(g)  # AUTO_FAIL：margin = 难度4
        ctrl.resolve_encounter_card("black_stars_rise_a")
        assert inv.horror == 4
        assert g.state.scenario.doom_on_agenda == 0

    def test_spires_of_carcosa_attach_and_doom(self):
        g, ctrl = _mk()
        loc = g.state.get_location("test_location")
        ctrl.resolve_encounter_card("spires_of_carcosa")
        assert ctrl.location_attachment_instance("test_location", "spires_of_carcosa")
        assert loc.doom == 2

    def test_spires_investigate_removes_doom_then_discards(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.card_data.skills.intellect = 10
        loc = g.state.get_location("test_location")
        ctrl.resolve_encounter_card("spires_of_carcosa")
        _pass_bag(g)
        assert ce.activate_spires_investigate(ctrl, "player") is True
        assert loc.doom == 1
        _pass_bag(g)
        assert ce.activate_spires_investigate(ctrl, "player") is True
        assert loc.doom == 0
        assert ctrl.location_attachment_instance("test_location", "spires_of_carcosa") is None

    def test_twisted_to_his_will_surges_without_doom(self):
        g, ctrl = _mk()
        r = ctrl.resolve_encounter_card("twisted_to_his_will")
        assert r.get("surge") is True

    def test_twisted_to_his_will_random_discard_two(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.card_data.skills.willpower = 1
        inv.hand = ["a", "b", "c"]
        g.state.scenario.doom_on_agenda = 2
        _fail_bag(g)
        ctrl.resolve_encounter_card("twisted_to_his_will")
        assert len(inv.hand) == 1
        assert len(inv.discard) == 2


class TestHauntingsAndHastur:
    def test_spirits_torment_attach_and_leave_horror(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        ctrl.resolve_encounter_card("spirits_torment")
        assert ctrl.location_attachment_instance("test_location", "spirits_torment")
        g.event_bus.emit(EventContext(
            game_state=g.state, event=GameEvent.MOVE_ACTION_INITIATED,
            investigator_id="player", location_id="elsewhere"))
        assert inv.horror == 1

    def test_spirits_torment_activate_places_clue_and_discards(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.clues = 1
        loc = g.state.get_location("test_location")
        clues0 = loc.clues
        ctrl.resolve_encounter_card("spirits_torment")
        assert ce.activate_spirits_torment(ctrl, "player") is True
        assert inv.clues == 0
        assert loc.clues == clues0 + 1
        assert ctrl.location_attachment_instance("test_location", "spirits_torment") is None

    def test_dance_of_yellow_king_surges_without_possessed(self):
        g, ctrl = _mk()
        r = ctrl.resolve_encounter_card("dance_of_the_yellow_king")
        assert r.get("surge") is True

    def test_dance_of_yellow_king_engages_and_attacks(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.card_data.skills.willpower = 1
        e = _add_enemy(g, "e1", "possessed_guest", ["possessed"])
        e.exhausted = True
        _fail_bag(g)
        ctrl.resolve_encounter_card("dance_of_the_yellow_king")
        assert "e1" in inv.threat_area
        assert e.exhausted is False
        assert inv.damage == 1 and inv.horror == 1  # 立即攻击（默认1伤1恐）


class TestCultAndDecay:
    def test_kings_edict_moves_clues_to_cultists(self):
        g, ctrl = _mk()
        loc = g.state.get_location("test_location")
        loc.clues = 2
        e = _add_enemy(g, "e1", "fanatic", ["cultist"])
        r = ctrl.resolve_encounter_card("the_kings_edict")
        assert r.get("surge") is None
        assert loc.clues == 1
        assert e.uses.get("clues") == 1
        assert g.state.scenario.vars.get("kings_edict_round") is not None

    def test_kings_edict_surges_when_no_clues_moved(self):
        g, ctrl = _mk()
        r = ctrl.resolve_encounter_card("the_kings_edict")
        assert r.get("surge") is True

    def test_ooze_and_filth_flag_cleared_at_round_end(self):
        g, ctrl = _mk()
        ctrl.resolve_encounter_card("ooze_and_filth")
        assert g.state.scenario.vars.get("ooze_and_filth") is True
        g.event_bus.emit(EventContext(game_state=g.state, event=GameEvent.ROUND_ENDS))
        assert "ooze_and_filth" not in g.state.scenario.vars

    def test_corrosion_discards_items_up_to_shroud(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        _register_asset(g, "item_a", cost=3, traits=["item"])
        _register_asset(g, "item_b", cost=1, traits=["item"])
        _add_asset_instance(g, inv, "i1", "item_a")
        inv.hand.append("item_b")
        r = ctrl.resolve_encounter_card("corrosion")  # test_location shroud=2
        assert r.get("surge") is None
        # 贪婪取最贵优先？不——按费用升序，item_b(1) 不够2 → 再 item_a(3)
        assert "item_b" in inv.discard and "i1" not in inv.play_area
        assert "item_a" in inv.discard

    def test_corrosion_surges_without_items(self):
        g, ctrl = _mk()
        r = ctrl.resolve_encounter_card("corrosion")
        assert r.get("surge") is True


class TestStranger:
    def test_marked_by_the_sign_fail_two_horror(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.card_data.skills.willpower = 1
        _fail_bag(g)
        ctrl.resolve_encounter_card("marked_by_the_sign")
        assert inv.horror == 2

    def test_marked_by_the_sign_direct_with_pallid_mask(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.card_data.skills.willpower = 1
        _add_enemy(g, "mitpm", "the_man_in_the_pallid_mask", ["humanoid", "elite"])
        _fail_bag(g)
        ctrl.resolve_encounter_card("marked_by_the_sign")
        assert inv.horror == 2

    def test_pale_mask_beckons_attacks_each_investigator(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        _add_enemy(g, "mitpm", "the_man_in_the_pallid_mask", ["humanoid", "elite"])
        r = ctrl.resolve_encounter_card("the_pale_mask_beckons")
        assert r["message"] == "the_pale_mask_beckons"
        assert inv.damage == 1 and inv.horror == 1

    def test_pale_mask_beckons_fetches_from_deck(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        g.register_card_data(make_enemy_data(id="the_man_in_the_pallid_mask",
                                             keywords=["humanoid", "elite"]))
        inv.deck = ["x", "the_man_in_the_pallid_mask", "y"]
        ctrl.resolve_encounter_card("the_pale_mask_beckons")
        spawned = [i for i, inst in g.state.cards_in_play.items()
                   if inst.card_id == "the_man_in_the_pallid_mask"]
        assert spawned and spawned[0] in inv.threat_area
        assert "the_man_in_the_pallid_mask" not in inv.deck


class TestEchoesOfThePast:
    def test_led_astray_pending_and_place_doom(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.clues = 1
        _add_enemy(g, "e1", "cultist_a", ["cultist"])
        r = ctrl.resolve_encounter_card("led_astray")
        assert r["pending"] is True
        assert g.state.scenario.vars["pending_choice"]["investigator_id"] == "player"
        g.state.scenario.vars.pop("pending_choice")
        doom0 = g.state.scenario.doom_on_agenda
        r = ctrl.resolve_encounter_card("led_astray", choice="place_doom")
        assert r["pending"] is False
        assert g.state.scenario.doom_on_agenda == doom0 + 1

    def test_led_astray_place_clue_on_cultist(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.clues = 2
        e = _add_enemy(g, "e1", "cultist_a", ["cultist"])
        ctrl.resolve_encounter_card("led_astray", choice="place_clue")
        assert inv.clues == 1
        assert e.uses.get("clues") == 1

    def test_led_astray_no_cultist_places_doom(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.clues = 2
        doom0 = g.state.scenario.doom_on_agenda
        r = ctrl.resolve_encounter_card("led_astray")
        assert r["pending"] is False
        assert g.state.scenario.doom_on_agenda == doom0 + 1

    def test_cults_search_moves_doom_to_agenda(self):
        g, ctrl = _mk()
        e = _add_enemy(g, "e1", "cultist_a", ["cultist"])
        e.doom = 2
        doom0 = g.state.scenario.doom_on_agenda
        ctrl.resolve_encounter_card("the_cults_search")
        assert e.doom == 0
        assert g.state.scenario.doom_on_agenda == doom0 + 2

    def test_cults_search_pulls_cultist_from_deck(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        g.register_card_data(make_enemy_data(id="fanatic", keywords=["cultist"]))
        _register_treachery(g, "filler")
        g.state.scenario.encounter_deck = ["filler", "fanatic"]
        ctrl.resolve_encounter_card("the_cults_search")
        spawned = [i for i, inst in g.state.cards_in_play.items()
                   if inst.card_id == "fanatic"]
        assert spawned and spawned[0] in inv.threat_area
        assert "fanatic" not in g.state.scenario.encounter_deck


class TestUnspeakableOath:
    def test_straitjacket_enters_threat_and_returns_slotted_assets(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        _register_asset(g, "coat", cost=1)
        _register_asset(g, "gun", cost=2)
        _add_asset_instance(g, inv, "a1", "coat", slots=[SlotType.BODY])
        _add_asset_instance(g, inv, "a2", "gun", slots=[SlotType.HAND])
        ctrl.resolve_encounter_card("straitjacket")
        threat = [i for i in inv.threat_area
                  if g.state.cards_in_play[i].card_id == "straitjacket"]
        assert threat
        assert "coat" in inv.hand and "gun" in inv.hand
        assert "a1" not in inv.play_area and "a2" not in inv.play_area

    def test_straitjacket_activate_discard(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.actions_remaining = 3
        ctrl.resolve_encounter_card("straitjacket")
        assert ce.activate_discard_straitjacket(ctrl, "player") is True
        assert inv.actions_remaining == 1
        assert not [i for i in inv.threat_area
                    if g.state.cards_in_play.get(i) and
                    g.state.cards_in_play[i].card_id == "straitjacket"]

    def test_gift_of_madness_enters_hand(self):
        for cid in ("gift_of_madness_a", "gift_of_madness_b"):
            g, ctrl = _mk()
            inv = g.state.get_investigator("player")
            ctrl.resolve_encounter_card(cid)
            assert cid in inv.hand
            assert g.state.scenario.vars["gift_of_madness"]["player"] == cid

    def test_gift_of_madness_activate_moves_set_aside_monster(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        g.state.scenario.vars["set_aside_monsters"] = ["asylum_gorger"]
        ctrl.resolve_encounter_card("gift_of_madness_a")
        assert ce.activate_gift_of_madness(ctrl, "player") is True
        assert g.state.scenario.vars["under_scenario_deck"] == ["asylum_gorger"]
        assert "gift_of_madness_a" in inv.discard

    def test_walls_closing_in_moves_set_aside_monster(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.card_data.skills.willpower = 1
        g.state.scenario.vars["set_aside_monsters"] = ["asylum_gorger"]
        _fail_bag(g)
        ctrl.resolve_encounter_card("walls_closing_in")
        assert g.state.scenario.vars["under_scenario_deck"] == ["asylum_gorger"]
        assert inv.horror == 0

    def test_walls_closing_in_horror_without_set_aside(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.card_data.skills.willpower = 1
        _fail_bag(g)  # AUTO_FAIL：margin = 难度(隐蔽)2
        ctrl.resolve_encounter_card("walls_closing_in")
        assert inv.horror == 2


class TestPhantomOfTruth:
    def test_twin_suns_removes_doom_on_fail(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.card_data.skills.intellect = 1
        g.state.scenario.doom_on_agenda = 2
        _fail_bag(g)
        ctrl.resolve_encounter_card("twin_suns")
        assert g.state.scenario.doom_on_agenda == 1
        assert inv.horror == 0

    def test_twin_suns_horror_without_doom(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.card_data.skills.intellect = 1
        _fail_bag(g)  # AUTO_FAIL：margin = 难度4
        ctrl.resolve_encounter_card("twin_suns")
        assert inv.horror == 4

    def test_deadly_fate_discards_until_enemy_and_draws(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.card_data.skills.willpower = 1
        _register_treachery(g, "filler")
        g.register_card_data(make_enemy_data(id="stealthy_byakhee", keywords=["byakhee"]))
        g.state.scenario.encounter_deck = ["filler", "stealthy_byakhee"]
        _fail_bag(g)
        ctrl.resolve_encounter_card("deadly_fate")
        assert "filler" in g.state.scenario.encounter_discard
        spawned = [i for i, inst in g.state.cards_in_play.items()
                   if inst.card_id == "stealthy_byakhee"]
        assert spawned and spawned[0] in inv.threat_area

    def test_deadly_fate_no_enemy_takes_horror(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.card_data.skills.willpower = 1
        _register_treachery(g, "filler")
        g.state.scenario.encounter_deck = ["filler"]
        _fail_bag(g)
        ctrl.resolve_encounter_card("deadly_fate")
        assert inv.horror == 1

    def test_torturous_chords_enters_threat_with_resources(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.card_data.skills.willpower = 1
        _fail_bag(g)  # AUTO_FAIL：margin = 难度5
        ctrl.resolve_encounter_card("torturous_chords")
        threat = [i for i in inv.threat_area
                  if g.state.cards_in_play[i].card_id == "torturous_chords"]
        assert threat
        assert g.state.scenario.vars["torturous_chords"]["player"] == 5

    def test_lost_soul_doubt_tests_intellect_vs_willpower(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.card_data.skills.intellect = 1
        inv.card_data.skills.willpower = 5
        g.state.scenario.vars["doubt"] = 2
        g.state.scenario.vars["conviction"] = 1
        _fail_bag(g)  # 智力1 vs 难度(意志)5 → 失败
        ctrl.resolve_encounter_card("lost_soul")
        assert inv.damage == 2

    def test_lost_soul_conviction_tests_willpower_vs_intellect(self):
        g, ctrl = _mk()
        inv = g.state.get_investigator("player")
        inv.card_data.skills.intellect = 5
        inv.card_data.skills.willpower = 1
        g.state.scenario.vars["doubt"] = 0
        g.state.scenario.vars["conviction"] = 3
        _fail_bag(g)  # 意志1 vs 难度(智力)5 → 失败
        ctrl.resolve_encounter_card("lost_soul")
        assert inv.damage == 2


class TestPallidMask:
    def test_eyes_in_the_walls_horror_per_point(self):
        g, ctrl = _mk("the_pallid_mask")
        inv = g.state.get_investigator("player")
        inv.card_data.skills.willpower = 1
        _fail_bag(g)  # AUTO_FAIL：margin = 难度3
        ctrl.resolve_encounter_card("eyes_in_the_walls")
        assert inv.horror == 3

    def test_shadow_behind_you_turn_end_discards_resources(self):
        g, ctrl = _mk("the_pallid_mask")
        inv = g.state.get_investigator("player")
        inv.resources = 4
        ctrl.resolve_encounter_card("the_shadow_behind_you")
        assert any(g.state.cards_in_play[i].card_id == "the_shadow_behind_you"
                   for i in inv.threat_area)
        g.event_bus.emit(EventContext(
            game_state=g.state, event=GameEvent.INVESTIGATOR_TURN_ENDS,
            investigator_id="player"))
        assert inv.resources == 0
        assert not any(i in g.state.cards_in_play and
                       g.state.cards_in_play[i].card_id == "the_shadow_behind_you"
                       for i in inv.threat_area)

    def test_shadow_behind_you_looked_avoids_penalty(self):
        g, ctrl = _mk("the_pallid_mask")
        inv = g.state.get_investigator("player")
        inv.resources = 4
        inv.actions_remaining = 3
        ctrl.resolve_encounter_card("the_shadow_behind_you")
        assert ce.activate_look_behind(ctrl, "player") is True
        assert inv.actions_remaining == 2
        g.event_bus.emit(EventContext(
            game_state=g.state, event=GameEvent.INVESTIGATOR_TURN_ENDS,
            investigator_id="player"))
        assert inv.resources == 4

    def test_shadow_behind_you_other_turn_end_keeps_hook(self):
        g, ctrl = _mk("the_pallid_mask")
        inv = g.state.get_investigator("player")
        inv.resources = 4
        ctrl.resolve_encounter_card("the_shadow_behind_you")
        # 另一调查员先结束回合：钩子不触发、不注销
        g.event_bus.emit(EventContext(
            game_state=g.state, event=GameEvent.INVESTIGATOR_TURN_ENDS,
            investigator_id="other"))
        assert inv.resources == 4
        g.event_bus.emit(EventContext(
            game_state=g.state, event=GameEvent.INVESTIGATOR_TURN_ENDS,
            investigator_id="player"))
        assert inv.resources == 0

    def test_pit_below_round_end_damage_and_discard(self):
        g, ctrl = _mk("the_pallid_mask")
        inv = g.state.get_investigator("player")
        ctrl.resolve_encounter_card("the_pit_below")
        assert ctrl.location_attachment_instance("test_location", "the_pit_below")
        g.event_bus.emit(EventContext(game_state=g.state, event=GameEvent.ROUND_ENDS))
        assert inv.damage == 3
        assert ctrl.location_attachment_instance("test_location", "the_pit_below") is None

    def test_pit_below_surges_when_already_attached(self):
        g, ctrl = _mk("the_pallid_mask")
        ctrl.resolve_encounter_card("the_pit_below")
        r = ctrl.resolve_encounter_card("the_pit_below")
        assert r.get("surge") is True


class TestBlackStarsRiseAndDimCarcosa:
    def test_crashing_floods_agenda_scales(self):
        g, ctrl = _mk("black_stars_rise")
        inv = g.state.get_investigator("player")
        inv.card_data.skills.agility = 1
        inv.actions_remaining = 3
        _fail_bag(g)
        ctrl.resolve_encounter_card("crashing_floods")
        assert inv.damage == 1 and inv.actions_remaining == 2

        g2, ctrl2 = _mk("black_stars_rise")
        inv2 = g2.state.get_investigator("player")
        inv2.card_data.skills.agility = 1
        inv2.actions_remaining = 3
        g2.state.scenario.current_agenda_index = 2
        _fail_bag(g2)
        ctrl2.resolve_encounter_card("crashing_floods")
        assert inv2.damage == 3 and inv2.actions_remaining == 0

    def test_worlds_merge_horror_and_discard(self):
        g, ctrl = _mk("black_stars_rise")
        inv = g.state.get_investigator("player")
        inv.card_data.skills.willpower = 1
        inv.hand = ["a", "b", "c"]
        g.state.scenario.current_agenda_index = 1
        _fail_bag(g)
        ctrl.resolve_encounter_card("worlds_merge")
        assert inv.horror == 2
        assert inv.hand == ["c"]
        assert inv.discard == ["a", "b"]

    def test_dismal_curse_two_damage(self):
        g, ctrl = _mk("dim_carcosa")
        inv = g.state.get_investigator("player")
        inv.card_data.skills.willpower = 1
        _fail_bag(g)
        ctrl.resolve_encounter_card("dismal_curse")
        assert inv.damage == 2

    def test_dismal_curse_four_damage_when_broken(self):
        g, ctrl = _mk("dim_carcosa")
        inv = g.state.get_investigator("player")
        inv.card_data.skills.willpower = 1
        inv.horror = 15  # > 2 * sanity(7)
        _fail_bag(g)
        ctrl.resolve_encounter_card("dismal_curse")
        assert inv.damage == 4

    def test_realm_of_madness_discards_by_cost(self):
        g, ctrl = _mk("dim_carcosa")
        inv = g.state.get_investigator("player")
        inv.horror = 2
        _register_asset(g, "asset_a", cost=3)
        inv.hand.append("asset_a")
        ctrl.resolve_encounter_card("realm_of_madness")
        assert "asset_a" in inv.discard
        assert inv.horror == 2

    def test_realm_of_madness_no_discard_takes_horror(self):
        g, ctrl = _mk("dim_carcosa")
        inv = g.state.get_investigator("player")
        inv.horror = 2
        ctrl.resolve_encounter_card("realm_of_madness")
        assert inv.horror == 4

    def test_final_act_doom_only_without_sanity(self):
        g, ctrl = _mk("dim_carcosa")
        inv = g.state.get_investigator("player")
        doom0 = g.state.scenario.doom_on_agenda
        r = ctrl.resolve_encounter_card("the_final_act")
        assert r.get("surge") is True
        assert g.state.scenario.doom_on_agenda == doom0  # 有神智 → 无毁灭

        inv.horror = inv.sanity  # 无剩余神智
        r = ctrl.resolve_encounter_card("the_final_act")
        assert g.state.scenario.doom_on_agenda == doom0 + 2

    def test_possession_enters_hand(self):
        for cid in ("possession_a", "possession_b", "possession_c"):
            g, ctrl = _mk("dim_carcosa")
            inv = g.state.get_investigator("player")
            ctrl.resolve_encounter_card(cid)
            assert cid in inv.hand
            assert g.state.scenario.vars["possession"]["player"] == cid

    def test_possession_kills_when_horror_exceeds_twice_sanity(self):
        g, ctrl = _mk("dim_carcosa")
        inv = g.state.get_investigator("player")
        inv.horror = 15  # > 2 * 7
        ctrl.resolve_encounter_card("possession_a")
        assert "player" in g.state.scenario.vars["killed_investigators"]
        assert inv.is_defeated

    def test_possession_b_activate_spend_five(self):
        g, ctrl = _mk("dim_carcosa")
        inv = g.state.get_investigator("player")
        inv.resources = 6
        ctrl.resolve_encounter_card("possession_b")
        assert ce.activate_discard_possession(ctrl, "player") is True
        assert inv.resources == 1
        assert "possession_b" in inv.discard

    def test_possession_c_activate_deals_damage(self):
        g, ctrl = _mk("dim_carcosa")
        inv = g.state.get_investigator("player")
        ctrl.resolve_encounter_card("possession_c")
        assert ce.activate_discard_possession(ctrl, "player") is True
        assert inv.damage == 2
        assert "possession_c" in inv.discard


class TestCoverage:
    def test_all_ptc_treacheries_handled_except_core_frozen_in_fear(self):
        """path_to_carcosa.json 中全部40张诡计：39张由 carcosa 分支处理，
        frozen_in_fear 由核心分支处理；两者都不能落到 (未实现)。"""
        import json
        from pathlib import Path
        data = json.loads((Path(__file__).resolve().parents[2]
                           / "data/encounter_cards/path_to_carcosa.json").read_text())
        ids = [c["id"] for c in data["cards"] if c.get("type") == "treachery"]
        assert len(ids) == 40
        for cid in ids:
            g, ctrl = _mk()
            g.state.scenario.vars.pop("pending_choice", None)
            log = ctrl.action_log
            log.clear()
            r = ctrl.resolve_encounter_card(cid)
            assert r is not None and r["message"] != "unhandled", cid
            assert not any("(未实现)" in m for m in log), cid
