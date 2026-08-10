"""Tests for difficulty-aware scenario chaos token effects (Hard/Expert).

Easy/Standard behavior is covered by test_scenario_tokens.py and
test_dunwich_tokens.py; these tests exercise the reference card back side.
"""

from backend.engine.event_bus import EventContext
from backend.models.enums import ChaosTokenType, GameEvent, Skill
from backend.tests.conftest import (
    make_asset_data,
    make_enemy_data,
    make_location_data,
)
from backend.tests.test_dunwich_tokens import _fail, _succeed
from backend.tests.test_scenario_tokens import _add_enemy, _make_game, _token


def _make_hard(scenario_id):
    g, ctrl = _make_game(scenario_id)
    g.state.scenario.vars["difficulty"] = "hard"
    return g, ctrl


def _register_enemy(game, card_id, keywords, damage=1, horror=1):
    cd = make_enemy_data(id=card_id, damage=damage, horror=horror)
    cd.keywords = keywords
    game.register_card_data(cd)
    return cd


class TestGatheringHardTokens:
    def test_skull_flat_minus2_regardless_of_ghouls(self):
        g, _ = _make_hard("the_gathering")
        _add_enemy(g, "e1", "ghoul_minion", ["ghoul"])
        ctx = _token(g, ChaosTokenType.SKULL)
        assert ctx.amount == -2  # 标准难度下为 -X（食屍鬼数量）

    def test_skull_fail_pulls_ghoul_from_encounter_deck(self):
        g, _ = _make_hard("the_gathering")
        _register_enemy(g, "ghoul_minion", ["ghoul"])
        g.state.scenario.encounter_deck = ["ghoul_minion"]
        ctx = _token(g, ChaosTokenType.SKULL)
        assert ctx.amount == -2
        _fail(g)
        assert g.state.scenario.encounter_deck == []
        inv = g.state.get_investigator("player")
        # 抽到后与调查员交战
        assert any(
            g.state.get_card_instance(iid).card_id == "ghoul_minion"
            for iid in inv.threat_area
        )

    def test_cultist_reveal_another_and_2_horror_on_fail(self):
        g, _ = _make_hard("the_gathering")
        g.chaos_bag.tokens = [ChaosTokenType.MINUS_2]
        inv = g.state.get_investigator("player")
        inv.horror = 0
        ctx = _token(g, ChaosTokenType.CULTIST)
        assert ctx.amount == -2  # 再揭示的 [-2]
        assert "再揭示" in ctx.extra["token_text"]
        _fail(g)
        assert inv.horror == 2

    def test_tablet_minus4_damage_and_horror_with_ghoul(self):
        g, _ = _make_hard("the_gathering")
        _add_enemy(g, "e1", "ghoul_minion", ["ghoul"])
        inv = g.state.get_investigator("player")
        ctx = _token(g, ChaosTokenType.TABLET)
        assert ctx.amount == -4
        assert inv.damage == 1
        assert inv.horror == 1


class TestMidnightMasksHardTokens:
    def test_skull_counts_total_doom_in_play(self):
        g, _ = _make_hard("the_midnight_masks")
        e = _add_enemy(g, "e1", "cultist_a", ["cultist"])
        e.doom = 2
        g.state.scenario.doom_on_agenda = 1
        ctx = _token(g, ChaosTokenType.SKULL)
        assert ctx.amount == -3  # 2 + 1（标准为“最多毁灭的异教徒”=-2）

    def test_cultist_doom_on_each_cultist(self):
        g, _ = _make_hard("the_midnight_masks")
        e1 = _add_enemy(g, "e1", "cultist_a", ["cultist"])
        e2 = _add_enemy(g, "e2", "cultist_b", ["cultist"])
        ctx = _token(g, ChaosTokenType.CULTIST)
        assert ctx.amount == -2
        assert e1.doom == 1 and e2.doom == 1

    def test_cultist_reveal_another_when_no_cultist(self):
        g, _ = _make_hard("the_midnight_masks")
        g.chaos_bag.tokens = [ChaosTokenType.MINUS_1]
        ctx = _token(g, ChaosTokenType.CULTIST)
        assert ctx.amount == -3  # -2 + 再揭示 [-1]

    def test_tablet_fail_places_all_clues(self):
        g, _ = _make_hard("the_midnight_masks")
        inv = g.state.get_investigator("player")
        inv.clues = 3
        loc = g.state.get_location("test_location")
        loc.clues = 0
        ctx = _token(g, ChaosTokenType.TABLET)
        assert ctx.amount == -4
        _fail(g)
        assert inv.clues == 0
        assert loc.clues == 3


class TestDevourerBelowHardTokens:
    def test_skull_minus3_and_pulls_monster_on_fail(self):
        g, _ = _make_hard("the_devourer_below")
        _register_enemy(g, "lugger", ["monster"])
        g.state.scenario.encounter_discard = ["lugger"]
        ctx = _token(g, ChaosTokenType.SKULL)
        assert ctx.amount == -3
        _fail(g)
        assert g.state.scenario.encounter_discard == []
        inv = g.state.get_investigator("player")
        assert any(
            g.state.get_card_instance(iid).card_id == "lugger"
            for iid in inv.threat_area
        )

    def test_cultist_minus4_two_doom_nearest_enemy(self):
        g, _ = _make_hard("the_devourer_below")
        e = _add_enemy(g, "e1", "some_enemy", ["monster"], engaged=True)
        ctx = _token(g, ChaosTokenType.CULTIST)
        assert ctx.amount == -4
        assert e.doom == 2

    def test_tablet_minus5_damage_and_horror_with_monster(self):
        g, _ = _make_hard("the_devourer_below")
        _add_enemy(g, "e1", "some_monster", ["monster"])
        inv = g.state.get_investigator("player")
        ctx = _token(g, ChaosTokenType.TABLET)
        assert ctx.amount == -5
        assert inv.damage == 1
        assert inv.horror == 1

    def test_elder_thing_minus7(self):
        g, _ = _make_hard("the_devourer_below")
        ctx = _token(g, ChaosTokenType.ELDER_THING)
        assert ctx.amount == -7


class TestExtracurricularHardTokens:
    def test_skull_minus2_discard5_on_fail(self):
        g, _ = _make_hard("extracurricular_activity")
        inv = g.state.get_investigator("player")
        inv.deck = ["c1", "c2", "c3", "c4", "c5", "c6"]
        ctx = _token(g, ChaosTokenType.SKULL)
        assert ctx.amount == -2
        _fail(g)
        assert inv.deck == ["c6"]
        assert inv.discard == ["c1", "c2", "c3", "c4", "c5"]

    def test_cultist_minus5_with_10_discards(self):
        g, _ = _make_hard("extracurricular_activity")
        inv = g.state.get_investigator("player")
        inv.discard = ["x"] * 10
        ctx = _token(g, ChaosTokenType.CULTIST)
        assert ctx.amount == -5

    def test_elder_thing_discards_3(self):
        g, _ = _make_hard("extracurricular_activity")
        g.register_card_data(make_asset_data(id="c1", cost=1))
        g.register_card_data(make_asset_data(id="c2", cost=1))
        g.register_card_data(make_asset_data(id="c3", cost=2))
        inv = g.state.get_investigator("player")
        inv.deck = ["c1", "c2", "c3", "c4"]
        ctx = _token(g, ChaosTokenType.ELDER_THING)
        assert ctx.amount == -4  # 1+1+2
        assert inv.deck == ["c4"]


class TestHouseAlwaysWinsHardTokens:
    def test_skull_autopays_3(self):
        g, _ = _make_hard("the_house_always_wins")
        inv = g.state.get_investigator("player")
        inv.resources = 4
        ctx = _token(g, ChaosTokenType.SKULL)
        assert ctx.amount == 0
        assert inv.resources == 1

    def test_skull_minus3_without_enough_resources(self):
        g, _ = _make_hard("the_house_always_wins")
        inv = g.state.get_investigator("player")
        inv.resources = 2
        ctx = _token(g, ChaosTokenType.SKULL)
        assert ctx.amount == -3
        assert inv.resources == 2

    def test_cultist_lose3_on_fail_not_gain_on_success(self):
        g, _ = _make_hard("the_house_always_wins")
        inv = g.state.get_investigator("player")
        inv.resources = 5
        ctx = _token(g, ChaosTokenType.CULTIST)
        assert ctx.amount == -3
        _fail(g)
        assert inv.resources == 2

        inv.resources = 5
        _token(g, ChaosTokenType.CULTIST)
        _succeed(g)
        assert inv.resources == 5  # 困难面没有“成功得3资源”

    def test_tablet_loses_3_immediately(self):
        g, _ = _make_hard("the_house_always_wins")
        inv = g.state.get_investigator("player")
        inv.resources = 5
        ctx = _token(g, ChaosTokenType.TABLET)
        assert ctx.amount == -2
        assert inv.resources == 2  # 无条件失去，不等失败


class TestMiskatonicMuseumHardTokens:
    def test_skull_minus2_without_horror(self):
        g, _ = _make_hard("the_miskatonic_museum")
        ctx = _token(g, ChaosTokenType.SKULL)
        assert ctx.amount == -2

    def test_skull_minus4_with_horror_at_location(self):
        g, _ = _make_hard("the_miskatonic_museum")
        _register_enemy(g, "hunting_horror", ["monster"])
        _add_enemy(g, "e1", "hunting_horror", ["monster"])
        ctx = _token(g, ChaosTokenType.SKULL)
        assert ctx.amount == -4

    def test_tablet_minus4_horror_attacks_at_location(self):
        g, _ = _make_hard("the_miskatonic_museum")
        _add_enemy(g, "e1", "hunting_horror", ["monster"])
        cd = g.state.card_database["hunting_horror"]
        cd.enemy_damage = 2
        cd.enemy_horror = 1
        inv = g.state.get_investigator("player")
        ctx = _token(g, ChaosTokenType.TABLET)
        assert ctx.amount == -4
        assert inv.damage == 2
        assert inv.horror == 1

    def test_cultist_minus3(self):
        g, _ = _make_hard("the_miskatonic_museum")
        ctx = _token(g, ChaosTokenType.CULTIST)
        assert ctx.amount == -3


class TestEssexCountyExpressHardTokens:
    def test_skull_agenda_number_plus_1(self):
        g, _ = _make_hard("essex_county_express")
        g.state.scenario.current_agenda_index = 1  # 密谋2
        ctx = _token(g, ChaosTokenType.SKULL)
        assert ctx.amount == -3  # 2+1

    def test_cultist_reveal_another(self):
        g, _ = _make_hard("essex_county_express")
        g.chaos_bag.tokens = [ChaosTokenType.ZERO]
        ctx = _token(g, ChaosTokenType.CULTIST)
        assert ctx.amount == 0
        assert "再揭示" in ctx.extra["token_text"]

    def test_tablet_doom_on_each_cultist(self):
        g, _ = _make_hard("essex_county_express")
        e1 = _add_enemy(g, "e1", "cultist_a", ["cultist"])
        e2 = _add_enemy(g, "e2", "cultist_b", ["cultist"])
        ctx = _token(g, ChaosTokenType.TABLET)
        assert ctx.amount == -4
        assert e1.doom == 1 and e2.doom == 1

    def test_elder_thing_discard_per_margin(self):
        g, _ = _make_hard("essex_county_express")
        inv = g.state.get_investigator("player")
        g.register_card_data(make_asset_data(id="h1"))
        g.register_card_data(make_asset_data(id="h2"))
        g.register_card_data(make_asset_data(id="h3"))
        inv.hand = ["h1", "h2", "h3"]
        ctx = _token(g, ChaosTokenType.ELDER_THING)
        assert ctx.amount == -3
        # 低于难度2点 → 弃2张
        g.event_bus.emit(EventContext(
            game_state=g.state, event=GameEvent.SKILL_TEST_FAILED,
            investigator_id="player", success=False,
            difficulty=4, modified_skill=2,
        ))
        assert len(inv.hand) == 1
        assert len(inv.discard) == 2


class TestBloodOnTheAltarHardTokens:
    def test_skull_no_cap(self):
        g, _ = _make_hard("blood_on_the_altar")
        for i in range(5):
            lid = f"loc_{i}"
            cd = make_location_data(id=lid, clue_value=0)
            g.register_card_data(cd)
            g.add_location(lid, cd, clues=0)
        # test_location 有3线索 + 5个无线索地点
        ctx = _token(g, ChaosTokenType.SKULL)
        assert ctx.amount == -5  # 标准难度最多 -4

    def test_tablet_reveal_another_anywhere(self):
        g, _ = _make_hard("blood_on_the_altar")
        g.chaos_bag.tokens = [ChaosTokenType.MINUS_3]
        ctx = _token(g, ChaosTokenType.TABLET)
        assert ctx.amount == -6  # -3 + 再揭示 [-3]（标准仅限隐藏密室）

    def test_elder_thing_doom_immediately(self):
        g, _ = _make_hard("blood_on_the_altar")
        g.state.scenario.doom_on_agenda = 0
        ctx = _token(g, ChaosTokenType.ELDER_THING)
        assert ctx.amount == -3
        assert g.state.scenario.doom_on_agenda == 1  # 无条件，不等失败


class TestUndimensionedHardTokens:
    def test_skull_minus2_per_brood(self):
        g, _ = _make_hard("undimensioned_and_unseen")
        _add_enemy(g, "e1", "brood_of_yog_sothoth", ["monster"])
        _add_enemy(g, "e2", "brood_of_yog_sothoth", ["monster"])
        ctx = _token(g, ChaosTokenType.SKULL)
        assert ctx.amount == -4

    def test_cultist_fail_damage_and_horror(self):
        g, _ = _make_hard("undimensioned_and_unseen")
        g.chaos_bag.tokens = [ChaosTokenType.ZERO]
        inv = g.state.get_investigator("player")
        _token(g, ChaosTokenType.CULTIST)
        _fail(g)
        assert inv.damage == 1
        assert inv.horror == 1

    def test_tablet_forces_auto_fail(self):
        g, _ = _make_hard("undimensioned_and_unseen")
        ctx = _token(g, ChaosTokenType.TABLET)
        assert ctx.extra.get("force_auto_fail") is True

    def test_tablet_auto_fail_via_engine(self):
        g, _ = _make_hard("undimensioned_and_unseen")
        g.chaos_bag.tokens = [ChaosTokenType.TABLET]
        inv_data = g.state.get_investigator("player").card_data
        result = g.skill_test_engine.run_test(
            investigator_id="player",
            skill_type=Skill.COMBAT,
            difficulty=1,  # 技能值必然达标，但石板强制自动失败
        )
        assert result.auto_fail
        assert not result.success


class TestWhereDoomAwaitsHardTokens:
    def test_skull_minus2(self):
        g, _ = _make_hard("where_doom_awaits")
        ctx = _token(g, ChaosTokenType.SKULL)
        assert ctx.amount == -2

    def test_tablet_minus3_agenda1(self):
        g, _ = _make_hard("where_doom_awaits")
        g.state.scenario.current_agenda_index = 0
        ctx = _token(g, ChaosTokenType.TABLET)
        assert ctx.amount == -3

    def test_tablet_auto_fail_agenda2(self):
        g, _ = _make_hard("where_doom_awaits")
        g.state.scenario.current_agenda_index = 1
        ctx = _token(g, ChaosTokenType.TABLET)
        assert ctx.extra.get("force_auto_fail") is True

    def test_elder_thing_discards_3(self):
        g, _ = _make_hard("where_doom_awaits")
        g.register_card_data(make_asset_data(id="c1", cost=2))
        g.register_card_data(make_asset_data(id="c2", cost=2))
        g.register_card_data(make_asset_data(id="c3", cost=1))
        inv = g.state.get_investigator("player")
        inv.deck = ["c1", "c2", "c3", "c4"]
        ctx = _token(g, ChaosTokenType.ELDER_THING)
        assert ctx.amount == -5  # 2+2+1
        assert inv.deck == ["c4"]


class TestLostInTimeAndSpaceHardTokens:
    def test_skull_no_cap(self):
        g, _ = _make_hard("lost_in_time_and_space")
        for i in range(6):
            lid = f"loc_{i}"
            cd = make_location_data(id=lid)
            cd.traits = ["異次元"]
            g.register_card_data(cd)
            g.add_location(lid, cd, clues=0)
        ctx = _token(g, ChaosTokenType.SKULL)
        assert ctx.amount == -6  # 标准难度最多 -5

    def test_tablet_minus5(self):
        g, _ = _make_hard("lost_in_time_and_space")
        ctx = _token(g, ChaosTokenType.TABLET)
        assert ctx.amount == -5

    def test_elder_thing_double_shroud(self):
        g, _ = _make_hard("lost_in_time_and_space")
        # test_location shroud=2
        ctx = _token(g, ChaosTokenType.ELDER_THING)
        assert ctx.amount == -4


class TestExpertAlsoUsesHardSide:
    def test_expert_gathering_skull(self):
        g, _ = _make_game("the_gathering")
        g.state.scenario.vars["difficulty"] = "expert"
        ctx = _token(g, ChaosTokenType.SKULL)
        assert ctx.amount == -2
