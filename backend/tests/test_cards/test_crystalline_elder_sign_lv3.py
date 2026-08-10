"""Tests for Crystalline Elder Sign (Level 3). (04235)

入场封印（+1或[elder_sign]，自动优先+1）；+1全部四项技能；离场返还标记。
"""

import pytest
from backend.cards.mystic.crystalline_elder_sign_lv3 import CrystallineElderSign
from backend.engine.event_bus import EventBus, EventContext
from backend.models.chaos import ChaosBag
from backend.models.enums import ChaosTokenType, GameEvent, Skill
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, ScenarioState,
)
from backend.tests.conftest import make_asset_data, make_investigator_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()
    inv_data = make_investigator_data(
        willpower=2, intellect=2, combat=2, agility=2)
    state.card_database[inv_data.id] = inv_data
    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1",
    )
    state.investigators["inv1"] = inv
    state.card_database["crystalline_elder_sign_lv3"] = make_asset_data(
        id="crystalline_elder_sign_lv3", name="Crystalline Elder Sign",
        traits=["item", "relic", "blessed"],
    )
    inst = CardInstance(
        instance_id="inst_ces", card_id="crystalline_elder_sign_lv3",
        owner_id="inv1", controller_id="inv1",
    )
    state.cards_in_play["inst_ces"] = inst
    inv.play_area.append("inst_ces")
    impl = CrystallineElderSign("inst_ces")
    impl.register(bus, "inst_ces")
    return state, bus, inv, inst, impl


def _enter(state, bus):
    bus.emit(EventContext(
        game_state=state, event=GameEvent.CARD_ENTERS_PLAY,
        investigator_id="inv1", target="inst_ces",
        extra={"card_id": "crystalline_elder_sign_lv3"},
    ))


class TestCrystallineElderSign:
    def test_seals_plus_1_preferentially(self, setup):
        state, bus, inv, inst, impl = setup
        bag = ChaosBag(tokens=[ChaosTokenType.PLUS_1, ChaosTokenType.ELDER_SIGN])
        impl.bind_chaos_bag(bag)
        _enter(state, bus)
        assert ChaosTokenType.PLUS_1 in bag.sealed
        assert ChaosTokenType.PLUS_1 not in bag.tokens
        assert ChaosTokenType.ELDER_SIGN in bag.tokens

    def test_seals_elder_sign_if_no_plus_1(self, setup):
        state, bus, inv, inst, impl = setup
        bag = ChaosBag(tokens=[ChaosTokenType.ELDER_SIGN, ChaosTokenType.ZERO])
        impl.bind_chaos_bag(bag)
        _enter(state, bus)
        assert ChaosTokenType.ELDER_SIGN in bag.sealed

    def test_skill_bonus_all_four(self, setup):
        state, bus, inv, inst, impl = setup
        for skill in (Skill.WILLPOWER, Skill.INTELLECT, Skill.COMBAT, Skill.AGILITY):
            ctx = EventContext(
                game_state=state, event=GameEvent.SKILL_VALUE_DETERMINED,
                investigator_id="inv1", skill_type=skill, amount=2,
            )
            bus.emit(ctx)
            assert ctx.amount == 3, skill

    def test_releases_token_on_leave(self, setup):
        state, bus, inv, inst, impl = setup
        bag = ChaosBag(tokens=[ChaosTokenType.PLUS_1])
        impl.bind_chaos_bag(bag)
        _enter(state, bus)
        assert bag.tokens == []
        bus.emit(EventContext(
            game_state=state, event=GameEvent.CARD_LEAVES_PLAY,
            investigator_id="inv1", target="inst_ces",
            extra={"card_id": "crystalline_elder_sign_lv3"},
        ))
        assert ChaosTokenType.PLUS_1 in bag.tokens
        assert bag.sealed == []
