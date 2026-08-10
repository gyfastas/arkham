"""Tests for Grounded (Level 1). (03113)

快速；场上限制1张沉稳；非直接恐惧必须先分配给情绪稳定；
【快速】法术卡检定时花1资源：+1技能值。
"""

import pytest
from backend.cards.mystic.grounded_lv1 import Grounded
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent, Skill
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, ScenarioState,
)
from backend.tests.conftest import make_asset_data, make_investigator_data


def _make_grounded(state, inv, instance_id="inst_grounded"):
    inst = CardInstance(
        instance_id=instance_id, card_id="grounded_lv1",
        owner_id="inv1", controller_id="inv1",
    )
    state.cards_in_play[instance_id] = inst
    inv.play_area.append(instance_id)
    return inst


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()

    inv_data = make_investigator_data()
    state.card_database[inv_data.id] = inv_data
    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1",
        resources=3,
    )
    state.investigators["inv1"] = inv

    state.card_database["grounded_lv1"] = make_asset_data(
        id="grounded_lv1", name="Grounded", cost=1,
        traits=["talent", "composure"], sanity=1,
    )
    state.card_database["fearless_lv0"] = make_asset_data(
        id="fearless_lv0", name="Fearless", cost=0,
        traits=["talent", "composure"], sanity=1,
    )
    state.card_database["shrivelling_lv0"] = make_asset_data(
        id="shrivelling_lv0", name="Shrivelling", traits=["spell"],
    )
    state.card_database["machete_lv0"] = make_asset_data(
        id="machete_lv0", name="Machete", traits=["item", "weapon"],
    )
    # 法术支援实例（作为检定来源）
    spell = CardInstance(
        instance_id="inst_shriv", card_id="shrivelling_lv0",
        owner_id="inv1", controller_id="inv1",
    )
    state.cards_in_play["inst_shriv"] = spell
    inv.play_area.append("inst_shriv")
    weapon = CardInstance(
        instance_id="inst_mach", card_id="machete_lv0",
        owner_id="inv1", controller_id="inv1",
    )
    state.cards_in_play["inst_mach"] = weapon
    inv.play_area.append("inst_mach")

    inst = _make_grounded(state, inv)
    impl = Grounded("inst_grounded")
    impl.register(bus, "inst_grounded")
    return state, bus, inv, inst, impl


class TestGroundedSoak:
    def test_soak_horror_before_investigator(self, setup):
        """非直接恐惧先分配给情绪稳定（至多其剩余神智1点）。"""
        state, bus, inv, inst, impl = setup
        ctx = EventContext(
            game_state=state, event=GameEvent.HORROR_ASSIGNED,
            investigator_id="inv1", amount=2,
        )
        bus.emit(ctx)
        assert inst.horror == 1
        assert ctx.amount == 1  # 调查员只承受剩余1点
        assert ctx.extra["grounded_soaked"] == 1

    def test_defeated_after_soaking_to_sanity(self, setup):
        """吸收满神智（1）后被击败：移出场地入弃牌堆。"""
        state, bus, inv, inst, impl = setup
        ctx = EventContext(
            game_state=state, event=GameEvent.HORROR_ASSIGNED,
            investigator_id="inv1", amount=1,
        )
        bus.emit(ctx)
        assert "inst_grounded" not in inv.play_area
        assert "inst_grounded" not in state.cards_in_play
        assert "grounded_lv1" in inv.discard

    def test_no_soak_when_not_in_play(self, setup):
        state, bus, inv, inst, impl = setup
        inv.play_area.remove("inst_grounded")
        ctx = EventContext(
            game_state=state, event=GameEvent.HORROR_ASSIGNED,
            investigator_id="inv1", amount=2,
        )
        bus.emit(ctx)
        assert ctx.amount == 2


class TestGroundedSpellPump:
    def _skill_ctx(self, state, source, amount=3):
        return EventContext(
            game_state=state, event=GameEvent.SKILL_VALUE_DETERMINED,
            investigator_id="inv1", skill_type=Skill.WILLPOWER,
            amount=amount, source=source,
        )

    def test_boost_on_spell_test(self, setup):
        """法术卡检定：花1资源+1技能值。"""
        state, bus, inv, inst, impl = setup
        assert impl.spend(state, "inv1") is True
        assert inv.resources == 2
        ctx = self._skill_ctx(state, "inst_shriv")
        bus.emit(ctx)
        assert ctx.amount == 4

    def test_boost_stacks(self, setup):
        """官方允许多次支付叠加：花2资源+2。"""
        state, bus, inv, inst, impl = setup
        impl.spend(state, "inv1")
        impl.spend(state, "inv1")
        ctx = self._skill_ctx(state, "inst_shriv")
        bus.emit(ctx)
        assert ctx.amount == 5
        assert inv.resources == 1

    def test_no_boost_on_non_spell_test(self, setup):
        """非法术卡来源的检定不加值（资源照样消耗，武装在检定结束清除）。"""
        state, bus, inv, inst, impl = setup
        impl.spend(state, "inv1")
        ctx = self._skill_ctx(state, "inst_mach")
        bus.emit(ctx)
        assert ctx.amount == 3
        bus.emit(EventContext(
            game_state=state, event=GameEvent.SKILL_TEST_ENDS,
            investigator_id="inv1",
        ))
        # 清除后再来一次法术检定也不加
        ctx2 = self._skill_ctx(state, "inst_shriv")
        bus.emit(ctx2)
        assert ctx2.amount == 3

    def test_spend_requires_resources(self, setup):
        state, bus, inv, inst, impl = setup
        inv.resources = 0
        assert impl.spend(state, "inv1") is False


class TestGroundedComposureLimit:
    def test_second_composure_discarded(self, setup):
        """场上已有沉稳卡时，新入场的情绪稳定被弃置。"""
        state, bus, inv, inst, impl = setup
        _make_grounded(state, inv, "inst_grounded2")
        impl2 = Grounded("inst_grounded2")
        impl2.register(bus, "inst_grounded2")
        ctx = EventContext(
            game_state=state, event=GameEvent.CARD_ENTERS_PLAY,
            investigator_id="inv1", target="inst_grounded2",
        )
        bus.emit(ctx)
        assert ctx.extra["grounded_discarded_limit"] is True
        assert "inst_grounded2" not in inv.play_area
        assert "inst_grounded" in inv.play_area  # 旧卡保留

    def test_first_composure_stays(self, setup):
        """唯一的沉稳卡正常入场。"""
        state, bus, inv, inst, impl = setup
        ctx = EventContext(
            game_state=state, event=GameEvent.CARD_ENTERS_PLAY,
            investigator_id="inv1", target="inst_grounded",
        )
        bus.emit(ctx)
        assert "inst_grounded" in inv.play_area
