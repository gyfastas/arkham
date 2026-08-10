"""Tests for Antiquary (Level 3) & Crafty (Level 3). (08124 / 08123)

使用(2资源)，每轮开始补充；对应特性卡的技能检定中花1卡上资源+1技能值。
"""

import pytest

from backend.cards.seeker.antiquary_lv3 import Antiquary
from backend.cards.seeker.crafty_lv3 import Crafty
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent, Skill
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, ScenarioState,
)
from backend.tests.conftest import make_asset_data, make_investigator_data


@pytest.fixture(params=["antiquary_lv3", "crafty_lv3"])
def setup(request):
    card_id = request.param
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()

    inv_data = make_investigator_data()
    state.card_database[inv_data.id] = inv_data
    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1",
    )
    state.investigators["inv1"] = inv

    # 数据文件中的双 s 键（"resourcess"）兼容性一并测试
    state.card_database[card_id] = make_asset_data(
        id=card_id, traits=["talent"], uses={"resourcess": 2},
    )
    inst = CardInstance(
        instance_id="inst_talent", card_id=card_id,
        owner_id="inv1", controller_id="inv1",
    )
    inst.uses = {"resourcess": 2}
    state.cards_in_play["inst_talent"] = inst
    inv.play_area.append("inst_talent")

    # 对应特性的检定来源卡（antiquary: relic / crafty: tool）
    trait = "relic" if card_id == "antiquary_lv3" else "tool"
    state.card_database["source_asset"] = make_asset_data(
        id="source_asset", traits=["item", trait],
    )
    source = CardInstance(
        instance_id="inst_source", card_id="source_asset",
        owner_id="inv1", controller_id="inv1",
    )
    state.cards_in_play["inst_source"] = source
    inv.play_area.append("inst_source")

    cls = Antiquary if card_id == "antiquary_lv3" else Crafty
    impl = cls("inst_talent")
    impl.register(bus, "inst_talent")
    return state, bus, inv, inst, impl


class TestSpendAndBoost:
    def test_spend_boosts_matching_trait_test(self, setup):
        """花1卡上资源：对应特性卡的检定+1技能值。"""
        state, bus, inv, inst, impl = setup
        assert impl.spend_resource(state, "inv1") is True
        assert inst.uses["resourcess"] == 1
        ctx = EventContext(
            game_state=state, event=GameEvent.SKILL_VALUE_DETERMINED,
            investigator_id="inv1", skill_type=Skill.INTELLECT,
            amount=3, source="inst_source",
        )
        bus.emit(ctx)
        assert ctx.amount == 4

    def test_no_boost_for_non_matching_source(self, setup):
        """非对应特性来源：不加值也不消耗武装。"""
        state, bus, inv, inst, impl = setup
        state.card_database["machete"] = make_asset_data(
            id="machete", traits=["item", "weapon"])
        machete = CardInstance(
            instance_id="inst_mach", card_id="machete",
            owner_id="inv1", controller_id="inv1",
        )
        state.cards_in_play["inst_mach"] = machete

        impl.spend_resource(state, "inv1")
        ctx = EventContext(
            game_state=state, event=GameEvent.SKILL_VALUE_DETERMINED,
            investigator_id="inv1", skill_type=Skill.COMBAT,
            amount=3, source="inst_mach",
        )
        bus.emit(ctx)
        assert ctx.amount == 3
        assert impl._armed == 1  # 武装未消耗

    def test_spend_requires_resources_on_card(self, setup):
        state, bus, inv, inst, impl = setup
        inst.uses["resourcess"] = 0
        assert impl.spend_resource(state, "inv1") is False


class TestReplenish:
    def test_round_begins_replenishes_to_full(self, setup):
        state, bus, inv, inst, impl = setup
        inst.uses["resourcess"] = 0
        bus.emit(EventContext(game_state=state, event=GameEvent.ROUND_BEGINS))
        assert inst.uses["resourcess"] == 2
