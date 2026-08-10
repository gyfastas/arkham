"""Tests for Astral Travel (Level 0). (03034)

移动到任意已揭示地点并揭示1个混乱标记；坏标记则丢弃一张道具/盟友支援
（不能则受1伤害）。
"""

import pytest
from backend.cards.mystic.astral_travel_lv0 import AstralTravel
from backend.engine.event_bus import EventBus, EventContext
from backend.models.chaos import ChaosBag
from backend.models.enums import ChaosTokenType, GameEvent
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, LocationState, ScenarioState,
)
from backend.tests.conftest import (
    make_asset_data, make_event_data, make_investigator_data,
    make_location_data,
)


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()

    inv_data = make_investigator_data()
    state.card_database[inv_data.id] = inv_data
    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1",
    )
    state.investigators["inv1"] = inv

    for loc_id, revealed in (("loc1", True), ("loc2", True), ("loc3", False)):
        loc_data = make_location_data(id=loc_id)
        state.card_database[loc_id] = loc_data
        state.locations[loc_id] = LocationState(
            location_id=loc_id, card_data=loc_data, revealed=revealed,
        )

    state.card_database["astral_travel_lv0"] = make_event_data(
        id="astral_travel_lv0", name="Astral Travel", cost=3,
    )
    state.card_database["machete_lv0"] = make_asset_data(
        id="machete_lv0", name="Machete", traits=["item", "weapon"],
    )
    state.card_database["holy_rosary_lv0"] = make_asset_data(
        id="holy_rosary_lv0", name="Holy Rosary", traits=["item", "charm"],
    )

    impl = AstralTravel("inst_at")
    impl.register(bus, "inst_at")
    return state, bus, inv, impl


def _play(bus, state, impl, tokens, **extra):
    bag = ChaosBag(tokens=list(tokens))
    bag.seed(1)
    impl.bind_chaos_bag(bag)
    ctx = EventContext(
        game_state=state, event=GameEvent.CARD_PLAYED,
        investigator_id="inv1", extra={"card_id": "astral_travel_lv0", **extra},
    )
    bus.emit(ctx)
    return ctx


def _add_asset(state, inv, instance_id, card_id):
    inst = CardInstance(
        instance_id=instance_id, card_id=card_id,
        owner_id="inv1", controller_id="inv1",
    )
    state.cards_in_play[instance_id] = inst
    inv.play_area.append(instance_id)
    return inst


class TestAstralTravel:
    def test_moves_to_revealed_location(self, setup):
        """移动到已揭示地点；数值标记无惩罚。"""
        state, bus, inv, impl = setup
        ctx = _play(bus, state, impl, [ChaosTokenType.MINUS_1])
        assert inv.location_id == "loc2"  # 第一个非当前已揭示地点
        assert ctx.extra["astral_travel_moved_to"] == "loc2"
        assert inv.damage == 0

    def test_explicit_destination(self, setup):
        state, bus, inv, impl = setup
        ctx = _play(bus, state, impl, [ChaosTokenType.ZERO],
                    destination="loc2")
        assert inv.location_id == "loc2"

    def test_unrevealed_destination_rejected(self, setup):
        """未揭示地点不能作为目标（loc3 未揭示，无其他已揭示目标时原地不动）。"""
        state, bus, inv, impl = setup
        ctx = _play(bus, state, impl, [ChaosTokenType.ZERO],
                    destination="loc3")
        assert inv.location_id == "loc1"
        assert "astral_travel_moved_to" not in ctx.extra

    def test_bad_token_discards_item_or_ally(self, setup):
        """坏标记：丢弃第一张道具/盟友支援。"""
        state, bus, inv, impl = setup
        _add_asset(state, inv, "inst_hr", "holy_rosary_lv0")
        _add_asset(state, inv, "inst_mach", "machete_lv0")
        ctx = _play(bus, state, impl, [ChaosTokenType.SKULL])
        assert ctx.extra["astral_travel_discarded"] == "holy_rosary_lv0"
        assert "inst_hr" not in inv.play_area
        assert "inst_hr" not in state.cards_in_play
        assert "holy_rosary_lv0" in inv.discard
        assert "inst_mach" in inv.play_area
        assert inv.damage == 0

    def test_bad_token_without_assets_takes_damage(self, setup):
        """坏标记且没有道具/盟友：受到1点伤害。"""
        state, bus, inv, impl = setup
        ctx = _play(bus, state, impl, [ChaosTokenType.TABLET])
        assert inv.damage == 1
        assert ctx.extra["astral_travel_damage"] == 1

    def test_bad_token_explicit_discard_target(self, setup):
        state, bus, inv, impl = setup
        _add_asset(state, inv, "inst_hr", "holy_rosary_lv0")
        _add_asset(state, inv, "inst_mach", "machete_lv0")
        ctx = _play(bus, state, impl, [ChaosTokenType.ELDER_THING],
                    discard_instance_id="inst_mach")
        assert ctx.extra["astral_travel_discarded"] == "machete_lv0"
        assert "inst_hr" in inv.play_area

    def test_auto_fail_token_triggers_penalty(self, setup):
        state, bus, inv, impl = setup
        _add_asset(state, inv, "inst_mach", "machete_lv0")
        ctx = _play(bus, state, impl, [ChaosTokenType.AUTO_FAIL])
        assert ctx.extra["astral_travel_discarded"] == "machete_lv0"
