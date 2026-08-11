"""Tests for The Innsmouth Conspiracy scenario chaos token effects.

直接驱动 backend.scenarios.tokens_tic 的 apply_token/on_fail/on_success
（该模块不挂事件总线，由调用方驱动；与 official_core 内部调度保持同一约定）。
数值以 data/encounter_cards/innsmouth_conspiracy.json 的 scenario 卡
text（Easy/Standard）/ back_text（Hard/Expert）为准。
"""

from backend.engine.event_bus import EventContext
from backend.models.enums import ChaosTokenType, GameEvent, Skill
from backend.scenarios.tokens_tic import apply_token, on_fail, on_success
from backend.tests.conftest import make_enemy_data, make_location_data
from backend.tests.test_scenario_tokens import _add_enemy, _make_game


def _mk(scenario_id, hard=False):
    g, ctrl = _make_game(scenario_id)
    g.state.scenario.vars["difficulty"] = "hard" if hard else "standard"
    return g, ctrl


def _add_location(game, loc_id, connections=(), traits=()):
    cd = make_location_data(id=loc_id, connections=list(connections))
    cd.traits = list(traits)
    game.register_card_data(cd)
    game.add_location(loc_id, cd, clues=0)
    return game.state.locations[loc_id]


class _Driver:
    """直接驱动 tokens_tic 三个入口的最小测试驱动器。"""

    def __init__(self, game, ctrl, inv_id="player"):
        self.g = game
        self.ctrl = ctrl
        self.inv_id = inv_id
        self.pending = set()
        self.success_pending = set()

    def token(self, token, skill_type=None, difficulty=3, source=None):
        ctx = EventContext(
            game_state=self.g.state,
            event=GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id=self.inv_id,
            chaos_token=token,
            amount=0,
            skill_type=skill_type,
            difficulty=difficulty,
            source=source,
        )
        inv = self.g.state.get_investigator(self.inv_id)
        handled = apply_token(self.ctrl, ctx, inv, self.pending, self.success_pending)
        assert handled
        return ctx

    def fail(self, difficulty=3, modified_skill=1, source=None):
        ctx = EventContext(
            game_state=self.g.state,
            event=GameEvent.SKILL_TEST_FAILED,
            investigator_id=self.inv_id,
            success=False,
            difficulty=difficulty,
            modified_skill=modified_skill,
            source=source,
        )
        on_fail(self.ctrl, ctx, self.pending)
        return ctx

    def succeed(self):
        ctx = EventContext(
            game_state=self.g.state,
            event=GameEvent.SKILL_TEST_SUCCESSFUL,
            investigator_id=self.inv_id,
            success=True,
        )
        on_success(self.ctrl, ctx, self.success_pending)
        return ctx


class TestDispatch:
    def test_returns_false_for_non_tic_scenario(self):
        g, ctrl = _mk("the_gathering")
        ctx = EventContext(
            game_state=g.state, event=GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="player", chaos_token=ChaosTokenType.SKULL, amount=0,
        )
        inv = g.state.get_investigator("player")
        assert apply_token(ctrl, ctx, inv, set(), set()) is False

    def test_returns_false_for_numeric_token(self):
        g, ctrl = _mk("the_pit_of_despair")
        ctx = EventContext(
            game_state=g.state, event=GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="player", chaos_token=ChaosTokenType.MINUS_2, amount=-2,
        )
        inv = g.state.get_investigator("player")
        assert apply_token(ctrl, ctx, inv, set(), set()) is False


class TestVanishingOfElinaHarperTokens:
    def test_skull_is_current_agenda_number(self):
        g, ctrl = _mk("the_vanishing_of_elina_harper")
        d = _Driver(g, ctrl)
        g.state.scenario.current_agenda_index = 0
        assert d.token(ChaosTokenType.SKULL).amount == -1
        g.state.scenario.current_agenda_index = 2
        assert d.token(ChaosTokenType.SKULL).amount == -3

    def test_skull_hard_is_agenda_number_plus_1(self):
        g, ctrl = _mk("the_vanishing_of_elina_harper", hard=True)
        d = _Driver(g, ctrl)
        g.state.scenario.current_agenda_index = 0
        assert d.token(ChaosTokenType.SKULL).amount == -2
        g.state.scenario.current_agenda_index = 1
        assert d.token(ChaosTokenType.SKULL).amount == -3

    def test_cultist_standard_dooms_nearest_enemy_on_fail(self):
        g, ctrl = _mk("the_vanishing_of_elina_harper")
        e = _add_enemy(g, "e1", "deep_one_hybrid", ["deep_one"], engaged=True)
        d = _Driver(g, ctrl)
        assert d.token(ChaosTokenType.CULTIST).amount == -2
        assert e.doom == 0
        d.fail()
        assert e.doom == 1

    def test_cultist_hard_dooms_immediately_and_extra_on_fail(self):
        g, ctrl = _mk("the_vanishing_of_elina_harper", hard=True)
        e = _add_enemy(g, "e1", "deep_one_hybrid", ["deep_one"], engaged=True)
        d = _Driver(g, ctrl)
        assert d.token(ChaosTokenType.CULTIST).amount == -2
        assert e.doom == 1
        d.fail()
        assert e.doom == 2

    def test_tablet_standard_horror_on_fail(self):
        g, ctrl = _mk("the_vanishing_of_elina_harper")
        inv = g.state.get_investigator("player")
        d = _Driver(g, ctrl)
        assert d.token(ChaosTokenType.TABLET).amount == -3
        assert inv.horror == 0
        d.fail()
        assert inv.horror == 1

    def test_tablet_hard_immediate_horror_and_damage_on_fail(self):
        g, ctrl = _mk("the_vanishing_of_elina_harper", hard=True)
        inv = g.state.get_investigator("player")
        d = _Driver(g, ctrl)
        assert d.token(ChaosTokenType.TABLET).amount == -3
        assert inv.horror == 1
        d.fail()
        assert inv.horror == 1
        assert inv.damage == 1

    def test_elder_thing_standard_places_clue_on_fail(self):
        g, ctrl = _mk("the_vanishing_of_elina_harper")
        inv = g.state.get_investigator("player")
        loc = g.state.get_location("test_location")
        inv.clues = 2
        loc.clues = 0
        d = _Driver(g, ctrl)
        assert d.token(ChaosTokenType.ELDER_THING).amount == -4
        assert (inv.clues, loc.clues) == (2, 0)
        d.fail()
        assert (inv.clues, loc.clues) == (1, 1)

    def test_elder_thing_hard_places_immediately_and_extra_on_fail(self):
        g, ctrl = _mk("the_vanishing_of_elina_harper", hard=True)
        inv = g.state.get_investigator("player")
        loc = g.state.get_location("test_location")
        inv.clues = 2
        loc.clues = 0
        d = _Driver(g, ctrl)
        assert d.token(ChaosTokenType.ELDER_THING).amount == -4
        assert (inv.clues, loc.clues) == (1, 1)
        d.fail()
        assert (inv.clues, loc.clues) == (0, 2)


class TestInTooDeepTokens:
    def _setup_grid(self, g):
        _add_location(g, "east1", connections=["test_location", "east2"])
        _add_location(g, "east2", connections=["east1"])
        g.state.get_location("test_location").card_data.connections = ["east1"]
        g.state.scenario.vars["grid_east"] = {
            "test_location": "east1",
            "east1": "east2",
        }

    def test_skull_per_eastern_location(self):
        g, ctrl = _mk("in_too_deep")
        self._setup_grid(g)
        d = _Driver(g, ctrl)
        assert d.token(ChaosTokenType.SKULL).amount == -2

    def test_skull_hard_doubles_per_eastern_location(self):
        g, ctrl = _mk("in_too_deep", hard=True)
        self._setup_grid(g)
        d = _Driver(g, ctrl)
        assert d.token(ChaosTokenType.SKULL).amount == -4

    def test_cultist_fail_moves_east_ignoring_barriers(self):
        g, ctrl = _mk("in_too_deep")
        self._setup_grid(g)
        g.state.scenario.vars["barriers"] = [frozenset(("test_location", "east1"))]
        inv = g.state.get_investigator("player")
        d = _Driver(g, ctrl)
        assert d.token(ChaosTokenType.CULTIST).amount == -2
        d.fail()
        assert inv.location_id == "east1"

    def test_cultist_hard_value(self):
        g, ctrl = _mk("in_too_deep", hard=True)
        self._setup_grid(g)
        d = _Driver(g, ctrl)
        assert d.token(ChaosTokenType.CULTIST).amount == -4

    def test_tablet_fail_places_barrier(self):
        g, ctrl = _mk("in_too_deep")
        self._setup_grid(g)
        d = _Driver(g, ctrl)
        assert d.token(ChaosTokenType.TABLET).amount == -3
        d.fail()
        barriers = g.state.scenario.vars["barriers"]
        assert frozenset(("test_location", "east1")) in [frozenset(b) for b in barriers]

    def test_tablet_hard_value(self):
        g, ctrl = _mk("in_too_deep", hard=True)
        self._setup_grid(g)
        d = _Driver(g, ctrl)
        assert d.token(ChaosTokenType.TABLET).amount == -5

    def test_elder_thing_per_barrier(self):
        g, ctrl = _mk("in_too_deep")
        self._setup_grid(g)
        g.state.scenario.vars["barriers"] = [
            frozenset(("test_location", "east1")),
            frozenset(("test_location", "east2")),
        ]
        d = _Driver(g, ctrl)
        assert d.token(ChaosTokenType.ELDER_THING).amount == -2

    def test_elder_thing_hard_doubles_per_barrier(self):
        g, ctrl = _mk("in_too_deep", hard=True)
        self._setup_grid(g)
        g.state.scenario.vars["barriers"] = [
            frozenset(("test_location", "east1")),
            frozenset(("test_location", "east2")),
        ]
        d = _Driver(g, ctrl)
        assert d.token(ChaosTokenType.ELDER_THING).amount == -4


class TestPitOfDespairTokens:
    def _set_flood(self, g, level):
        g.state.scenario.vars["flood_levels"] = {"test_location": level}

    def test_skull_scales_with_flood_level(self):
        g, ctrl = _mk("the_pit_of_despair")
        d = _Driver(g, ctrl)
        assert d.token(ChaosTokenType.SKULL).amount == -1
        self._set_flood(g, 1)
        assert d.token(ChaosTokenType.SKULL).amount == -2
        self._set_flood(g, 2)
        assert d.token(ChaosTokenType.SKULL).amount == -3

    def test_skull_hard_scales_with_flood_level(self):
        g, ctrl = _mk("the_pit_of_despair", hard=True)
        d = _Driver(g, ctrl)
        assert d.token(ChaosTokenType.SKULL).amount == -2
        self._set_flood(g, 1)
        assert d.token(ChaosTokenType.SKULL).amount == -3
        self._set_flood(g, 2)
        assert d.token(ChaosTokenType.SKULL).amount == -4

    def test_cultist_standard_damage_on_fail_when_flooded(self):
        g, ctrl = _mk("the_pit_of_despair")
        self._set_flood(g, 1)
        inv = g.state.get_investigator("player")
        d = _Driver(g, ctrl)
        assert d.token(ChaosTokenType.CULTIST).amount == -2
        assert inv.damage == 0
        d.fail()
        assert inv.damage == 1

    def test_cultist_standard_no_effect_when_unflooded(self):
        g, ctrl = _mk("the_pit_of_despair")
        inv = g.state.get_investigator("player")
        d = _Driver(g, ctrl)
        assert d.token(ChaosTokenType.CULTIST).amount == -2
        d.fail()
        assert inv.damage == 0

    def test_cultist_hard_damage_immediately_when_flooded(self):
        g, ctrl = _mk("the_pit_of_despair", hard=True)
        self._set_flood(g, 2)
        inv = g.state.get_investigator("player")
        d = _Driver(g, ctrl)
        assert d.token(ChaosTokenType.CULTIST).amount == -2
        assert inv.damage == 1

    def test_tablet_standard_horror_on_fail_with_key(self):
        g, ctrl = _mk("the_pit_of_despair")
        g.state.scenario.vars["keys_controlled"] = ["key_red"]
        inv = g.state.get_investigator("player")
        d = _Driver(g, ctrl)
        assert d.token(ChaosTokenType.TABLET).amount == -2
        assert inv.horror == 0
        d.fail()
        assert inv.horror == 1

    def test_tablet_hard_immediate_horror_with_key(self):
        g, ctrl = _mk("the_pit_of_despair", hard=True)
        g.state.scenario.vars["keys_controlled"] = ["key_red"]
        inv = g.state.get_investigator("player")
        d = _Driver(g, ctrl)
        assert d.token(ChaosTokenType.TABLET).amount == -2
        assert inv.horror == 1

    def test_elder_thing_standard_spawns_amalgam_on_fail(self):
        g, ctrl = _mk("the_pit_of_despair")
        g.register_card_data(make_enemy_data(id="the_amalgam"))
        g.state.scenario.vars["amalgam_in_depths"] = True
        inv = g.state.get_investigator("player")
        d = _Driver(g, ctrl)
        assert d.token(ChaosTokenType.ELDER_THING).amount == -3
        assert not inv.threat_area
        d.fail()
        assert any(
            g.state.get_card_instance(iid).card_id == "the_amalgam"
            for iid in inv.threat_area
        )

    def test_elder_thing_hard_spawns_amalgam_immediately(self):
        g, ctrl = _mk("the_pit_of_despair", hard=True)
        g.register_card_data(make_enemy_data(id="the_amalgam"))
        g.state.scenario.vars["amalgam_in_depths"] = True
        inv = g.state.get_investigator("player")
        d = _Driver(g, ctrl)
        assert d.token(ChaosTokenType.ELDER_THING).amount == -3
        assert any(
            g.state.get_card_instance(iid).card_id == "the_amalgam"
            for iid in inv.threat_area
        )


class TestDevilReefTokens:
    def test_skull_per_controlled_key(self):
        g, ctrl = _mk("devil_reef")
        g.state.scenario.vars["keys_controlled"] = ["k1", "k2"]
        d = _Driver(g, ctrl)
        assert d.token(ChaosTokenType.SKULL).amount == -2

    def test_skull_hard_adds_one(self):
        g, ctrl = _mk("devil_reef", hard=True)
        g.state.scenario.vars["keys_controlled"] = ["k1", "k2"]
        d = _Driver(g, ctrl)
        assert d.token(ChaosTokenType.SKULL).amount == -3

    def test_cultist_standard_deep_one_engages_on_fail(self):
        g, ctrl = _mk("devil_reef")
        _add_enemy(g, "e1", "deep_one_raider", ["deep_one"])
        inv = g.state.get_investigator("player")
        loc = g.state.get_location("test_location")
        d = _Driver(g, ctrl)
        ctx = d.token(ChaosTokenType.CULTIST, skill_type=Skill.COMBAT, source="e1")
        assert ctx.amount == -2
        assert "e1" in loc.enemies  # 揭示时尚未交战
        d.fail(source="e1")
        assert "e1" in inv.threat_area
        assert "e1" not in loc.enemies

    def test_cultist_hard_deep_one_engages_immediately(self):
        g, ctrl = _mk("devil_reef", hard=True)
        _add_enemy(g, "e1", "deep_one_raider", ["deep_one"])
        inv = g.state.get_investigator("player")
        d = _Driver(g, ctrl)
        ctx = d.token(ChaosTokenType.CULTIST, skill_type=Skill.AGILITY, source="e1")
        assert ctx.amount == -3
        assert "e1" in inv.threat_area

    def test_cultist_no_engage_for_non_deep_one(self):
        g, ctrl = _mk("devil_reef")
        _add_enemy(g, "e1", "hybrid_horror", ["monster"])
        inv = g.state.get_investigator("player")
        d = _Driver(g, ctrl)
        ctx = d.token(ChaosTokenType.CULTIST, skill_type=Skill.COMBAT, source="e1")
        assert ctx.amount == -2
        d.fail(source="e1")
        assert "e1" not in inv.threat_area

    def test_tablet_standard_damage_on_fail_outside_vehicle(self):
        g, ctrl = _mk("devil_reef")
        inv = g.state.get_investigator("player")
        d = _Driver(g, ctrl)
        assert d.token(ChaosTokenType.TABLET).amount == -3
        d.fail()
        assert inv.damage == 1

    def test_tablet_standard_no_damage_in_vehicle(self):
        g, ctrl = _mk("devil_reef")
        g.state.scenario.vars["in_vehicle"] = ["player"]
        inv = g.state.get_investigator("player")
        d = _Driver(g, ctrl)
        assert d.token(ChaosTokenType.TABLET).amount == -3
        d.fail()
        assert inv.damage == 0

    def test_tablet_hard_damage_immediately_outside_vehicle(self):
        g, ctrl = _mk("devil_reef", hard=True)
        inv = g.state.get_investigator("player")
        d = _Driver(g, ctrl)
        assert d.token(ChaosTokenType.TABLET).amount == -4
        assert inv.damage == 1

    def test_elder_thing_standard_horror_on_fail_with_key_on_location(self):
        g, ctrl = _mk("devil_reef")
        g.state.scenario.vars["keys_on_locations"] = {"test_location": ["k1"]}
        inv = g.state.get_investigator("player")
        d = _Driver(g, ctrl)
        assert d.token(ChaosTokenType.ELDER_THING).amount == -4
        assert inv.horror == 0
        d.fail()
        assert inv.horror == 1

    def test_elder_thing_hard_immediate_horror_with_key_on_location(self):
        g, ctrl = _mk("devil_reef", hard=True)
        g.state.scenario.vars["keys_on_locations"] = {"test_location": ["k1"]}
        inv = g.state.get_investigator("player")
        d = _Driver(g, ctrl)
        assert d.token(ChaosTokenType.ELDER_THING).amount == -5
        assert inv.horror == 1


class TestHorrorInHighGearTokens:
    def test_skull_scales_with_road_deck(self):
        g, ctrl = _mk("horror_in_high_gear")
        d = _Driver(g, ctrl)
        g.state.scenario.vars["road_deck"] = ["r"] * 7
        assert d.token(ChaosTokenType.SKULL).amount == -1
        g.state.scenario.vars["road_deck"] = ["r"] * 6
        assert d.token(ChaosTokenType.SKULL).amount == -3

    def test_skull_hard_scales_with_road_deck(self):
        g, ctrl = _mk("horror_in_high_gear", hard=True)
        d = _Driver(g, ctrl)
        g.state.scenario.vars["road_deck"] = ["r"] * 7
        assert d.token(ChaosTokenType.SKULL).amount == -2
        g.state.scenario.vars["road_deck"] = ["r"] * 6
        assert d.token(ChaosTokenType.SKULL).amount == -4

    def test_cultist_fail_places_clues_per_margin(self):
        g, ctrl = _mk("horror_in_high_gear")
        inv = g.state.get_investigator("player")
        loc = g.state.get_location("test_location")
        inv.clues = 2
        loc.clues = 0
        d = _Driver(g, ctrl)
        assert d.token(ChaosTokenType.CULTIST).amount == -1
        d.fail(difficulty=4, modified_skill=1)  # margin 3，但只有2线索
        assert inv.clues == 0
        assert loc.clues == 2

    def test_cultist_hard_value(self):
        g, ctrl = _mk("horror_in_high_gear", hard=True)
        d = _Driver(g, ctrl)
        assert d.token(ChaosTokenType.CULTIST).amount == -2

    def test_tablet_fail_loses_resources_per_margin(self):
        g, ctrl = _mk("horror_in_high_gear")
        inv = g.state.get_investigator("player")
        inv.resources = 5
        d = _Driver(g, ctrl)
        assert d.token(ChaosTokenType.TABLET).amount == -2
        d.fail(difficulty=4, modified_skill=2)  # margin 2
        assert inv.resources == 3

    def test_tablet_hard_value(self):
        g, ctrl = _mk("horror_in_high_gear", hard=True)
        d = _Driver(g, ctrl)
        assert d.token(ChaosTokenType.TABLET).amount == -3

    def test_elder_thing_standard_hunter_on_fail(self):
        g, ctrl = _mk("horror_in_high_gear")
        _add_location(g, "east1", connections=["test_location"])
        _add_enemy(g, "e1", "pursuing_car", ["monster"], location="east1")
        loc = g.state.get_location("test_location")
        d = _Driver(g, ctrl)
        assert d.token(ChaosTokenType.ELDER_THING).amount == -4
        assert "e1" in g.state.get_location("east1").enemies
        d.fail()
        assert "e1" in loc.enemies
        assert "e1" not in g.state.get_location("east1").enemies

    def test_elder_thing_hard_hunter_immediately(self):
        g, ctrl = _mk("horror_in_high_gear", hard=True)
        _add_location(g, "east1", connections=["test_location"])
        _add_enemy(g, "e1", "pursuing_car", ["monster"], location="east1")
        loc = g.state.get_location("test_location")
        d = _Driver(g, ctrl)
        assert d.token(ChaosTokenType.ELDER_THING).amount == -4
        assert "e1" in loc.enemies


class TestALightInTheFogTokens:
    def _set_flood(self, g, level):
        g.state.scenario.vars["flood_levels"] = {"test_location": level}

    def test_skull_no_extra_reveal_when_unflooded(self):
        g, ctrl = _mk("a_light_in_the_fog")
        g.chaos_bag.tokens = [ChaosTokenType.MINUS_2]
        d = _Driver(g, ctrl)
        assert d.token(ChaosTokenType.SKULL).amount == -1

    def test_skull_reveals_extra_when_flooded(self):
        g, ctrl = _mk("a_light_in_the_fog")
        self._set_flood(g, 1)
        g.chaos_bag.tokens = [ChaosTokenType.MINUS_2]
        d = _Driver(g, ctrl)
        assert d.token(ChaosTokenType.SKULL).amount == -3  # -1 + 追加[-2]

    def test_skull_hard_reveals_extra_when_flooded(self):
        g, ctrl = _mk("a_light_in_the_fog", hard=True)
        self._set_flood(g, 2)
        g.chaos_bag.tokens = [ChaosTokenType.MINUS_1]
        d = _Driver(g, ctrl)
        assert d.token(ChaosTokenType.SKULL).amount == -3  # -2 + 追加[-1]

    def test_cultist_fail_increases_flood_level(self):
        g, ctrl = _mk("a_light_in_the_fog")
        d = _Driver(g, ctrl)
        assert d.token(ChaosTokenType.CULTIST).amount == -2
        d.fail()
        assert g.state.scenario.vars["flood_levels"]["test_location"] == 1

    def test_cultist_hard_fail_at_full_flood_takes_horror(self):
        g, ctrl = _mk("a_light_in_the_fog", hard=True)
        self._set_flood(g, 2)
        inv = g.state.get_investigator("player")
        d = _Driver(g, ctrl)
        assert d.token(ChaosTokenType.CULTIST).amount == -2
        d.fail()
        assert g.state.scenario.vars["flood_levels"]["test_location"] == 2
        assert inv.horror == 1

    def test_tablet_fail_flooded_damage(self):
        g, ctrl = _mk("a_light_in_the_fog")
        self._set_flood(g, 1)
        inv = g.state.get_investigator("player")
        d = _Driver(g, ctrl)
        assert d.token(ChaosTokenType.TABLET).amount == -3
        d.fail()
        assert inv.damage == 1

    def test_tablet_hard_fail_flooded_damage_2(self):
        g, ctrl = _mk("a_light_in_the_fog", hard=True)
        self._set_flood(g, 1)
        inv = g.state.get_investigator("player")
        d = _Driver(g, ctrl)
        assert d.token(ChaosTokenType.TABLET).amount == -3
        d.fail()
        assert inv.damage == 2

    def test_tablet_fail_unflooded_no_damage(self):
        g, ctrl = _mk("a_light_in_the_fog")
        inv = g.state.get_investigator("player")
        d = _Driver(g, ctrl)
        assert d.token(ChaosTokenType.TABLET).amount == -3
        d.fail()
        assert inv.damage == 0

    def test_elder_thing_standard_moves_ready_enemy_on_fail(self):
        g, ctrl = _mk("a_light_in_the_fog")
        _add_location(g, "east1", connections=["test_location"])
        e1 = _add_enemy(g, "e1", "deep_one_raider", ["deep_one"], location="east1")
        e2 = _add_enemy(g, "e2", "deep_one_guard", ["deep_one"], location="east1")
        e2.exhausted = True
        d = _Driver(g, ctrl)
        assert d.token(ChaosTokenType.ELDER_THING).amount == -4
        d.fail()
        loc = g.state.get_location("test_location")
        assert "e1" in loc.enemies  # 就绪敌人移动
        assert "e2" in g.state.get_location("east1").enemies  # 横置敌人不动

    def test_elder_thing_hard_moves_nearest_unengaged_immediately(self):
        g, ctrl = _mk("a_light_in_the_fog", hard=True)
        _add_location(g, "east1", connections=["test_location"])
        e2 = _add_enemy(g, "e2", "deep_one_guard", ["deep_one"], location="east1")
        e2.exhausted = True
        d = _Driver(g, ctrl)
        assert d.token(ChaosTokenType.ELDER_THING).amount == -4
        loc = g.state.get_location("test_location")
        assert "e2" in loc.enemies  # 困难面不要求就绪，立即移动


class TestLairOfDagonTokens:
    def test_skull_per_key_on_scenario_card(self):
        g, ctrl = _mk("the_lair_of_dagon")
        g.state.scenario.vars["keys_on_scenario_card"] = ["k1", "k2"]
        d = _Driver(g, ctrl)
        assert d.token(ChaosTokenType.SKULL).amount == -2

    def test_skull_hard_two_per_key(self):
        g, ctrl = _mk("the_lair_of_dagon", hard=True)
        g.state.scenario.vars["keys_on_scenario_card"] = ["k1", "k2"]
        d = _Driver(g, ctrl)
        assert d.token(ChaosTokenType.SKULL).amount == -4

    def test_cultist_standard_zero_reveals_extra(self):
        g, ctrl = _mk("the_lair_of_dagon")
        g.chaos_bag.tokens = [ChaosTokenType.MINUS_1]
        d = _Driver(g, ctrl)
        ctx = d.token(ChaosTokenType.CULTIST)
        assert ctx.amount == -1  # 0 + 追加[-1]
        assert not ctx.extra.get("force_auto_fail")

    def test_cultist_hard_minus2_reveals_extra(self):
        g, ctrl = _mk("the_lair_of_dagon", hard=True)
        g.chaos_bag.tokens = [ChaosTokenType.MINUS_1]
        d = _Driver(g, ctrl)
        ctx = d.token(ChaosTokenType.CULTIST)
        assert ctx.amount == -3  # -2 + 追加[-1]
        assert not ctx.extra.get("force_auto_fail")

    def test_cultist_curse_reveal_auto_fails(self):
        g, ctrl = _mk("the_lair_of_dagon")
        g.chaos_bag.tokens = [ChaosTokenType.CURSE]
        d = _Driver(g, ctrl)
        ctx = d.token(ChaosTokenType.CULTIST)
        assert ctx.amount == -2  # 诅咒本身 -2
        assert ctx.extra.get("force_auto_fail") is True

    def test_tablet_standard_places_keys_on_fail(self):
        g, ctrl = _mk("the_lair_of_dagon")
        g.state.scenario.vars["keys_controlled"] = ["k1", "k2"]
        d = _Driver(g, ctrl)
        assert d.token(ChaosTokenType.TABLET).amount == -3
        d.fail()
        assert g.state.scenario.vars["keys_controlled"] == []
        assert g.state.scenario.vars["keys_on_locations"]["test_location"] == ["k1", "k2"]

    def test_tablet_hard_places_keys_and_damage_immediately(self):
        g, ctrl = _mk("the_lair_of_dagon", hard=True)
        g.state.scenario.vars["keys_controlled"] = ["k1"]
        inv = g.state.get_investigator("player")
        d = _Driver(g, ctrl)
        assert d.token(ChaosTokenType.TABLET).amount == -3
        assert g.state.scenario.vars["keys_controlled"] == []
        assert g.state.scenario.vars["keys_on_locations"]["test_location"] == ["k1"]
        assert inv.damage == 1

    def test_elder_thing_standard_adds_curse_on_fail(self):
        g, ctrl = _mk("the_lair_of_dagon")
        d = _Driver(g, ctrl)
        assert d.token(ChaosTokenType.ELDER_THING).amount == -4
        assert ChaosTokenType.CURSE not in g.chaos_bag.tokens
        d.fail()
        assert g.chaos_bag.tokens.count(ChaosTokenType.CURSE) == 1

    def test_elder_thing_hard_adds_two_curses_immediately(self):
        g, ctrl = _mk("the_lair_of_dagon", hard=True)
        d = _Driver(g, ctrl)
        assert d.token(ChaosTokenType.ELDER_THING).amount == -4
        assert g.chaos_bag.tokens.count(ChaosTokenType.CURSE) == 2


class TestIntoTheMaelstromTokens:
    def _add_yha_locations(self, g, n):
        for i in range(n):
            _add_location(g, f"yha{i}", traits=["y'ha-nthlei"])

    def test_skull_base_values(self):
        g, ctrl = _mk("into_the_maelstrom")
        d = _Driver(g, ctrl)
        assert d.token(ChaosTokenType.SKULL).amount == -1

    def test_skull_four_unflooded_yha_nthlei(self):
        g, ctrl = _mk("into_the_maelstrom")
        self._add_yha_locations(g, 4)
        d = _Driver(g, ctrl)
        assert d.token(ChaosTokenType.SKULL).amount == -3

    def test_skull_flooded_yha_nthlei_not_counted(self):
        g, ctrl = _mk("into_the_maelstrom")
        self._add_yha_locations(g, 4)
        g.state.scenario.vars["flood_levels"] = {"yha0": 1}
        d = _Driver(g, ctrl)
        assert d.token(ChaosTokenType.SKULL).amount == -1  # 只剩3个未淹没

    def test_skull_hard_values(self):
        g, ctrl = _mk("into_the_maelstrom", hard=True)
        d = _Driver(g, ctrl)
        assert d.token(ChaosTokenType.SKULL).amount == -2
        self._add_yha_locations(g, 4)
        assert d.token(ChaosTokenType.SKULL).amount == -4

    def test_cultist_fail_dooms_current_agenda(self):
        g, ctrl = _mk("into_the_maelstrom")
        d = _Driver(g, ctrl)
        assert d.token(ChaosTokenType.CULTIST).amount == -3
        assert g.state.scenario.doom_on_agenda == 0
        d.fail()
        assert g.state.scenario.doom_on_agenda == 1

    def test_cultist_hard_value(self):
        g, ctrl = _mk("into_the_maelstrom", hard=True)
        d = _Driver(g, ctrl)
        assert d.token(ChaosTokenType.CULTIST).amount == -4

    def test_tablet_fail_increases_flood_when_possible(self):
        g, ctrl = _mk("into_the_maelstrom")
        inv = g.state.get_investigator("player")
        d = _Driver(g, ctrl)
        assert d.token(ChaosTokenType.TABLET).amount == -4
        d.fail()
        assert g.state.scenario.vars["flood_levels"]["test_location"] == 1
        assert inv.damage == 0

    def test_tablet_fail_takes_damage_at_full_flood(self):
        g, ctrl = _mk("into_the_maelstrom")
        g.state.scenario.vars["flood_levels"] = {"test_location": 2}
        inv = g.state.get_investigator("player")
        d = _Driver(g, ctrl)
        assert d.token(ChaosTokenType.TABLET).amount == -4
        d.fail()
        assert inv.damage == 1

    def test_tablet_hard_value(self):
        g, ctrl = _mk("into_the_maelstrom", hard=True)
        d = _Driver(g, ctrl)
        assert d.token(ChaosTokenType.TABLET).amount == -5

    def test_elder_thing_fail_horror_with_key_on_location(self):
        g, ctrl = _mk("into_the_maelstrom")
        g.state.scenario.vars["keys_on_locations"] = {"test_location": ["k1"]}
        inv = g.state.get_investigator("player")
        d = _Driver(g, ctrl)
        assert d.token(ChaosTokenType.ELDER_THING).amount == -5
        assert inv.horror == 0
        d.fail()
        assert inv.horror == 1

    def test_elder_thing_hard_value_and_fail_horror(self):
        g, ctrl = _mk("into_the_maelstrom", hard=True)
        g.state.scenario.vars["keys_on_locations"] = {"test_location": ["k1"]}
        inv = g.state.get_investigator("player")
        d = _Driver(g, ctrl)
        assert d.token(ChaosTokenType.ELDER_THING).amount == -6
        d.fail()
        assert inv.horror == 1

    def test_elder_thing_no_key_no_horror(self):
        g, ctrl = _mk("into_the_maelstrom")
        inv = g.state.get_investigator("player")
        d = _Driver(g, ctrl)
        assert d.token(ChaosTokenType.ELDER_THING).amount == -5
        d.fail()
        assert inv.horror == 0
