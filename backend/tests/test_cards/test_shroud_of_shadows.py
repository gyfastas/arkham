"""Tests for Shroud of Shadows (lv0 / lv4)."""

import pytest

from backend.cards.mystic.shroud_of_shadows_lv0 import ShroudOfShadows
from backend.cards.mystic.shroud_of_shadows_lv4 import ShroudOfShadowsLv4
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import ChaosTokenType, GameEvent, Skill
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, LocationState, ScenarioState,
)
from backend.tests.conftest import (
    make_asset_data, make_enemy_data, make_investigator_data,
    make_location_data,
)


def _setup(impl_cls, card_id, willpower=5, agility=2, elite=False):
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()

    inv_data = make_investigator_data(willpower=willpower, agility=agility)
    state.card_database[inv_data.id] = inv_data
    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1")
    state.investigators["inv1"] = inv

    loc1 = make_location_data(id="loc1", connections=["loc2"])
    loc2 = make_location_data(id="loc2", connections=["loc1"])
    state.card_database["loc1"] = loc1
    state.card_database["loc2"] = loc2
    state.locations["loc1"] = LocationState(location_id="loc1", card_data=loc1)
    state.locations["loc2"] = LocationState(location_id="loc2", card_data=loc2)

    enemy_data = make_enemy_data(keywords=["elite"] if elite else [])
    state.card_database["test_enemy"] = enemy_data
    enemy = CardInstance(
        instance_id="enemy1", card_id="test_enemy",
        owner_id="scenario", controller_id="scenario",
    )
    state.cards_in_play["enemy1"] = enemy

    state.card_database[card_id] = make_asset_data(
        id=card_id, uses={"chargess": 3})
    inst = CardInstance(
        instance_id="inst1", card_id=card_id,
        owner_id="inv1", controller_id="inv1",
    )
    inst.uses = {"chargess": 3}
    state.cards_in_play["inst1"] = inst
    inv.play_area.append("inst1")

    impl = impl_cls("inst1")
    impl.register(bus, "inst1")
    return state, bus, inv, inst, impl, enemy


def _emit(bus, state, event, **kwargs):
    ctx = EventContext(game_state=state, event=event, investigator_id="inv1", **kwargs)
    bus.emit(ctx)
    return ctx


class TestShroudOfShadowsLv0:
    CID = "shroud_of_shadows_lv0"

    def test_activate_spends_charge(self):
        state, bus, inv, inst, impl, _ = _setup(ShroudOfShadows, self.CID)
        assert impl.activate(state, "inv1", "enemy1") is True
        assert inst.uses["chargess"] == 2

    def test_willpower_substitute(self):
        state, bus, inv, inst, impl, _ = _setup(ShroudOfShadows, self.CID)
        impl.activate(state, "inv1", "enemy1")
        ctx = _emit(bus, state, GameEvent.SKILL_VALUE_DETERMINED,
                    skill_type=Skill.AGILITY, amount=2)
        assert ctx.amount == 5  # 意志代替敏捷，无额外加值

    def test_move_non_elite_enemy_on_evade(self):
        state, bus, inv, inst, impl, enemy = _setup(ShroudOfShadows, self.CID)
        impl.activate(state, "inv1", "enemy1")
        state.locations["loc1"].enemies.append("enemy1")  # 躲避成功后引擎放置
        ctx = _emit(bus, state, GameEvent.ENEMY_EVADED, enemy_id="enemy1")
        assert "enemy1" not in state.locations["loc1"].enemies
        assert "enemy1" in state.locations["loc2"].enemies
        assert ctx.extra["shroud_of_shadows_lv0_moved_enemy"] == "loc2"

    def test_elite_enemy_not_moved(self):
        state, bus, inv, inst, impl, enemy = _setup(
            ShroudOfShadows, self.CID, elite=True)
        impl.activate(state, "inv1", "enemy1")
        state.locations["loc1"].enemies.append("enemy1")
        _emit(bus, state, GameEvent.ENEMY_EVADED, enemy_id="enemy1")
        assert "enemy1" in state.locations["loc1"].enemies

    def test_curse_token_places_charge(self):
        state, bus, inv, inst, impl, _ = _setup(ShroudOfShadows, self.CID)
        impl.activate(state, "inv1", "enemy1")  # 3 -> 2
        _emit(bus, state, GameEvent.CHAOS_TOKEN_RESOLVED,
              chaos_token=ChaosTokenType.CURSE)
        ctx = _emit(bus, state, GameEvent.SKILL_TEST_ENDS, success=True)
        assert inst.uses["chargess"] == 3  # +1充能
        assert ctx.extra["shroud_of_shadows_lv0_charges_gained"] == 1


class TestShroudOfShadowsLv4:
    CID = "shroud_of_shadows_lv4"

    def test_willpower_substitute_plus_two(self):
        state, bus, inv, inst, impl, _ = _setup(ShroudOfShadowsLv4, self.CID)
        impl.activate(state, "inv1", "enemy1")
        ctx = _emit(bus, state, GameEvent.SKILL_VALUE_DETERMINED,
                    skill_type=Skill.AGILITY, amount=2)
        assert ctx.amount == 7  # 5意志 + 2

    def test_charge_per_curse(self):
        state, bus, inv, inst, impl, _ = _setup(ShroudOfShadowsLv4, self.CID)
        impl.activate(state, "inv1", "enemy1")  # 3 -> 2
        for _ in range(2):
            _emit(bus, state, GameEvent.CHAOS_TOKEN_RESOLVED,
                  chaos_token=ChaosTokenType.CURSE)
        ctx = _emit(bus, state, GameEvent.SKILL_TEST_ENDS, success=True)
        assert inst.uses["chargess"] == 4  # 每个 curse +1
        assert ctx.extra["shroud_of_shadows_lv4_charges_gained"] == 2
