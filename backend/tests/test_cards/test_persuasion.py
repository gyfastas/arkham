"""Tests for Persuasion (Level 0)."""

import pytest
from backend.cards.seeker.persuasion_lv0 import Persuasion
from backend.engine.event_bus import EventBus, EventContext
from backend.models.chaos import ChaosBag
from backend.models.enums import ChaosTokenType, GameEvent
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, LocationState, ScenarioState,
)
from backend.tests.conftest import (
    make_enemy_data, make_investigator_data, make_location_data,
)


def _humanoid(id="cultist", keywords=None, horror=1):
    data = make_enemy_data(id=id, fight=2, health=2, evade=2, horror=horror,
                           keywords=keywords or [])
    data.traits = ["humanoid", "cultist"]
    return data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()
    bag = ChaosBag()
    bag.seed(42)

    inv_data = make_investigator_data(intellect=4)
    state.card_database[inv_data.id] = inv_data
    loc_data = make_location_data()
    state.card_database[loc_data.id] = loc_data
    state.card_database["cultist"] = _humanoid()

    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="test_location",
    )
    state.investigators["inv1"] = inv
    loc = LocationState(location_id="test_location", card_data=loc_data, clues=0)
    state.locations["test_location"] = loc

    enemy = CardInstance(
        instance_id="e1", card_id="cultist",
        owner_id="scenario", controller_id="scenario",
    )
    state.cards_in_play["e1"] = enemy
    inv.threat_area.append("e1")

    impl = Persuasion("pers_1")
    impl.register(bus, "pers_1")
    impl.bind_chaos_bag(bag)
    return state, bus, bag, inv, loc, impl


def _play(state, bus, **extra):
    ctx = EventContext(
        game_state=state,
        event=GameEvent.CARD_PLAYED,
        investigator_id="inv1",
        extra={"card_id": "persuasion_lv0", **extra},
    )
    bus.emit(ctx)
    return ctx


class TestPersuasion:
    def test_success_shuffles_enemy_into_encounter_deck(self, setup):
        """成功（智力4 对 3+恐惧1=4，0标记）：敌人洗回遭遇牌堆。"""
        state, bus, bag, inv, loc, impl = setup
        bag.tokens = [ChaosTokenType.ZERO]
        state.scenario.encounter_deck = ["x1", "x2"]

        ctx = _play(state, bus)
        assert ctx.extra["persuasion_success"] is True
        assert ctx.extra["persuasion_shuffled"] == "e1"
        assert "e1" not in state.cards_in_play
        assert "e1" not in inv.threat_area
        assert "cultist" in state.scenario.encounter_deck
        assert len(state.scenario.encounter_deck) == 3

    def test_failure_enemy_stays(self, setup):
        """失败：敌人留在原地。"""
        state, bus, bag, inv, loc, impl = setup
        bag.tokens = [ChaosTokenType.AUTO_FAIL]

        ctx = _play(state, bus)
        assert ctx.extra["persuasion_success"] is False
        assert "e1" in inv.threat_area

    def test_elite_evaded_instead(self, setup):
        """精英敌人：成功时改为自动躲避（不入遭遇牌堆）。"""
        state, bus, bag, inv, loc, impl = setup
        state.card_database["elite_cultist"] = _humanoid(
            id="elite_cultist", keywords=["elite"])
        elite = CardInstance(
            instance_id="e2", card_id="elite_cultist",
            owner_id="scenario", controller_id="scenario",
        )
        state.cards_in_play["e2"] = elite
        loc.enemies.append("e2")
        bag.tokens = [ChaosTokenType.ZERO]

        ctx = _play(state, bus, enemy_instance_id="e2")
        assert ctx.extra["persuasion_success"] is True
        assert ctx.extra["persuasion_evaded"] == "e2"
        assert elite.exhausted is True
        assert "e2" in state.cards_in_play  # 未离场
        assert "e2" in loc.enemies
        assert "elite_cultist" not in state.scenario.encounter_deck

    def test_non_humanoid_not_a_valid_target(self, setup):
        """非类人敌人不可选。"""
        state, bus, bag, inv, loc, impl = setup
        beast = make_enemy_data(id="beast")
        beast.traits = ["monster", "creature"]
        state.card_database["beast"] = beast
        b = CardInstance(
            instance_id="e3", card_id="beast",
            owner_id="scenario", controller_id="scenario",
        )
        state.cards_in_play["e3"] = b

        ctx = _play(state, bus, enemy_instance_id="e3")
        assert "persuasion_success" not in ctx.extra
