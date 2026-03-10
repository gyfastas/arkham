"""Regression tests for importing official core set scenarios."""

from __future__ import annotations

from backend.engine.game import Game
from backend.scenarios.official_core import apply_scenario_to_game, ScenarioController
from backend.tests.conftest import make_investigator_data


def _make_game_with_scenario(scenario_id: str) -> Game:
    g = Game(scenario_id)
    inv_data = make_investigator_data()
    g.register_card_data(inv_data)

    apply_scenario_to_game(g, scenario_id, seed=42)

    # Place investigator at scenario start
    from backend.scenarios.official_core import load_scenario_definition

    scen = load_scenario_definition(scenario_id)
    g.add_investigator("player", inv_data, deck=[], starting_location=scen["start_location"])
    return g


class TestScenarioImport:
    def test_the_gathering_import_basics(self):
        g = _make_game_with_scenario("the_gathering")
        assert "study" in g.state.locations
        assert g.state.get_location("study").connections
        assert len(g.state.scenario.agenda_deck) == 3
        assert len(g.state.scenario.act_deck) == 3
        assert len(g.state.scenario.encounter_deck) > 0

        from backend.models.enums import CardType

        enemies = [cd for cd in g.state.card_database.values() if cd.type == CardType.ENEMY]
        assert enemies
        assert any(e.enemy_fight is not None for e in enemies)

    def test_midnight_masks_import_basics(self):
        g = _make_game_with_scenario("the_midnight_masks")
        assert "rivertown" in g.state.locations
        assert len(g.state.scenario.agenda_deck) == 1
        assert len(g.state.scenario.act_deck) == 1
        assert len(g.state.scenario.encounter_deck) > 0

    def test_devourer_below_import_basics(self):
        g = _make_game_with_scenario("the_devourer_below")
        assert "main_path" in g.state.locations
        assert len(g.state.scenario.agenda_deck) == 3
        assert len(g.state.scenario.act_deck) == 3
        assert len(g.state.scenario.encounter_deck) > 0


class TestScenarioController:
    def test_ancient_evils_adds_doom_and_advances_agenda_when_needed(self):
        g = _make_game_with_scenario("the_gathering")
        ctrl = ScenarioController(g)
        ctrl.attach()

        threshold = g.state.scenario.effective_doom_threshold
        g.state.scenario.doom_on_agenda = threshold - 1

        # Ancient Evils adds +1 doom and can immediately advance agenda
        ctrl.resolve_encounter_card("ancient_evils")

        assert g.state.scenario.current_agenda_index == 1
        # MythosPhase clears doom when the agenda advances.
        assert g.state.scenario.doom_on_agenda == 0

    def test_midnight_masks_resign_branching(self):
        g = _make_game_with_scenario("the_midnight_masks")
        ctrl = ScenarioController(g)

        g.state.scenario.vars["cultists_defeated"] = 0
        assert ctrl.resign() == "R3"

        g.state.scenario.vars["cultists_defeated"] = 3
        assert ctrl.resign() == "R2"

        g.state.scenario.vars["cultists_defeated"] = 6
        assert ctrl.resign() == "R1"

    def test_the_gathering_advance_act_spawns_ghoul_priest(self):
        g = _make_game_with_scenario("the_gathering")
        ctrl = ScenarioController(g)
        ctrl.attach()
        inv = g.state.get_investigator("player")

        # Give enough clues for Act 1
        inv.clues = 2
        assert g.state.scenario.current_act.id == "trapped"
        ok = ctrl.advance_act("player")
        assert ok
        # Ghoul Priest should be spawned (as an enemy instance)
        assert any(ci.card_id == "ghoul_priest" for ci in g.state.cards_in_play.values())


class TestCoreTreacheryCoverage:
    def test_all_core_scenarios_treachery_ids_are_handled(self):
        """"全覆盖"：3个核心剧本会用到的所有诡计卡都有可执行的结算逻辑。

        这里不追求逐字规则完全一致，但至少保证：
        - 不会抛异常
        - 需要选择的卡会进入 pending_choice
        - 技能检定类卡会造成某种可观测状态变化（伤害/恐惧/线索/doom/挂载等）
        """
        treacheries = [
            "grasping_hands",
            "crypt_chill",
            "obscuring_fog",
            "dissonant_voices",
            "frozen_in_fear",
            "rotting_remains",
            "ancient_evils",
            "mysterious_chanting",
            "locked_door",
            "false_lead",
            "hunting_shadow",
            "on_wings_of_darkness",
            "um_rdhoth_s_wrath",
            "dreams_of_r_lyeh",
            "the_yellow_sign",
            "offer_of_power",
        ]

        g = _make_game_with_scenario("the_gathering")
        ctrl = ScenarioController(g)
        ctrl.attach()

        # Force all skill tests to fail deterministically
        from backend.models.enums import ChaosTokenType

        g.chaos_bag.tokens = [ChaosTokenType.AUTO_FAIL]

        inv = g.state.get_investigator("player")
        inv.clues = 2
        inv.resources = 5

        # add a dummy asset to be discarded by Crypt Chill
        from backend.models.enums import CardType, PlayerClass
        from backend.models.state import CardData

        g.register_card_data(
            CardData(
                id="dummy_asset",
                name="Dummy",
                name_cn="测试支援",
                type=CardType.ASSET,
                card_class=PlayerClass.NEUTRAL,
                cost=0,
            )
        )
        inv.hand.append("dummy_asset")

        # Play it into play area so Crypt Chill can discard it
        g.action_resolver.perform_action("player", __import__("backend.models.enums", fromlist=["Action"]).Action.PLAY, card_id="dummy_asset")

        for cid in treacheries:
            g.state.scenario.vars.pop("pending_choice", None)
            before = (
                inv.damage,
                inv.horror,
                inv.clues,
                g.state.scenario.doom_on_agenda,
                len(inv.play_area),
                len(g.state.cards_in_play),
            )
            r = ctrl.resolve_encounter_card(cid)
            assert r is not None
            # choice cards should go pending if no choice supplied
            if cid in {"hunting_shadow", "offer_of_power"}:
                assert g.state.scenario.vars.get("pending_choice")
                # resolve a default choice to ensure it finishes
                opt = g.state.scenario.vars["pending_choice"]["options"][0]["id"]
                g.state.scenario.vars.pop("pending_choice", None)
                ctrl.resolve_encounter_card(cid, choice=opt)
            after = (
                inv.damage,
                inv.horror,
                inv.clues,
                g.state.scenario.doom_on_agenda,
                len(inv.play_area),
                len(g.state.cards_in_play),
            )
            assert before != after or cid in {"dissonant_voices", "frozen_in_fear", "dreams_of_r_lyeh", "obscuring_fog", "locked_door"}
