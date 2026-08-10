"""Tests for Recharge (Level 2). (03197)

选择同地点调查员控制的一张法术/遗物支援并揭示混乱标记：
坏标记丢弃该支援，否则+3充能。
"""

import pytest
from backend.cards.mystic.recharge_lv2 import Recharge
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
    loc_data = make_location_data(id="loc1")
    state.card_database["loc1"] = loc_data
    state.locations["loc1"] = LocationState(
        location_id="loc1", card_data=loc_data, revealed=True,
    )

    state.card_database["recharge_lv2"] = make_event_data(
        id="recharge_lv2", name="Recharge", cost=0,
    )
    state.card_database["shrivelling_lv0"] = make_asset_data(
        id="shrivelling_lv0", name="Shrivelling", traits=["spell"],
        uses={"charges": 4},
    )
    state.card_database["spirit_athame_lv1"] = make_asset_data(
        id="spirit_athame_lv1", name="Spirit Athame",
        traits=["item", "relic", "weapon", "melee"],
    )
    state.card_database["machete_lv0"] = make_asset_data(
        id="machete_lv0", name="Machete", traits=["item", "weapon"],
    )

    impl = Recharge("inst_recharge")
    impl.register(bus, "inst_recharge")
    return state, bus, inv, impl


def _add_asset(state, inv, instance_id, card_id, charges=None):
    inst = CardInstance(
        instance_id=instance_id, card_id=card_id,
        owner_id="inv1", controller_id="inv1",
    )
    if charges is not None:
        inst.uses = {"charges": charges}
    state.cards_in_play[instance_id] = inst
    inv.play_area.append(instance_id)
    return inst


def _play(bus, state, impl, tokens, **extra):
    bag = ChaosBag(tokens=list(tokens))
    bag.seed(1)
    impl.bind_chaos_bag(bag)
    ctx = EventContext(
        game_state=state, event=GameEvent.CARD_PLAYED,
        investigator_id="inv1", extra={"card_id": "recharge_lv2", **extra},
    )
    bus.emit(ctx)
    return ctx


class TestRecharge:
    def test_good_token_adds_3_charges(self, setup):
        """数值标记：目标法术支援+3充能。"""
        state, bus, inv, impl = setup
        spell = _add_asset(state, inv, "inst_shriv", "shrivelling_lv0", charges=1)
        ctx = _play(bus, state, impl, [ChaosTokenType.MINUS_2])
        assert spell.uses["charges"] == 4
        assert ctx.extra["recharge_charges_added"] == 3
        assert ctx.extra["recharge_target"] == "inst_shriv"

    def test_bad_token_discards_target(self, setup):
        """坏标记：丢弃目标支援。"""
        state, bus, inv, impl = setup
        _add_asset(state, inv, "inst_shriv", "shrivelling_lv0", charges=1)
        ctx = _play(bus, state, impl, [ChaosTokenType.CULTIST])
        assert ctx.extra["recharge_discarded"] == "shrivelling_lv0"
        assert "inst_shriv" not in inv.play_area
        assert "inst_shriv" not in state.cards_in_play
        assert "shrivelling_lv0" in inv.discard

    def test_prefers_asset_with_charges(self, setup):
        """自动目标：优先带充能的法术/遗物（+3充能才有意义）。"""
        state, bus, inv, impl = setup
        _add_asset(state, inv, "inst_athame", "spirit_athame_lv1")  # 遗物无充能
        spell = _add_asset(state, inv, "inst_shriv", "shrivelling_lv0", charges=0)
        ctx = _play(bus, state, impl, [ChaosTokenType.ZERO])
        assert ctx.extra["recharge_target"] == "inst_shriv"
        assert spell.uses["charges"] == 3

    def test_relic_is_valid_target(self, setup):
        """遗物也是合法目标（显式指定）。"""
        state, bus, inv, impl = setup
        athame = _add_asset(state, inv, "inst_athame", "spirit_athame_lv1")
        ctx = _play(bus, state, impl, [ChaosTokenType.PLUS_1],
                    target_instance_id="inst_athame")
        assert ctx.extra["recharge_target"] == "inst_athame"
        assert athame.uses["charges"] == 3

    def test_non_spell_relic_not_targeted(self, setup):
        """普通道具（砍刀）不是合法目标：无合法目标时效果不发动。"""
        state, bus, inv, impl = setup
        _add_asset(state, inv, "inst_mach", "machete_lv0")
        ctx = _play(bus, state, impl, [ChaosTokenType.ZERO])
        assert "recharge_target" not in ctx.extra
        assert "inst_mach" in inv.play_area

    def test_targets_other_investigator_asset_at_location(self, setup):
        """同地点其他调查员控制的支援也可选。"""
        state, bus, inv, impl = setup
        inv2_data = make_investigator_data(id="inv2", name="Second")
        state.card_database["inv2"] = inv2_data
        inv2 = InvestigatorState(
            investigator_id="inv2", card_data=inv2_data, location_id="loc1",
        )
        state.investigators["inv2"] = inv2
        spell = _add_asset(state, inv2, "inst_shriv2", "shrivelling_lv0", charges=2)
        ctx = _play(bus, state, impl, [ChaosTokenType.ZERO],
                    target_instance_id="inst_shriv2")
        assert spell.uses["charges"] == 5
