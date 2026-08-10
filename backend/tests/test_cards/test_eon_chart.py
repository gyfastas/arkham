"""Tests for Eon Chart (Level 1 & 4). (08098 / 08100)

[快速]你的回合中横置+1秘密：执行移动/躲避/调查（lv4为两项不同行动）。
"""

import pytest

from backend.cards.seeker.eon_chart_lv1 import EonChart
from backend.cards.seeker.eon_chart_lv4 import EonChartLv4
from backend.engine.event_bus import EventBus, EventContext
from backend.models.chaos import ChaosBag
from backend.models.enums import ChaosTokenType, GameEvent
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, LocationState, ScenarioState,
)
from backend.tests.conftest import (
    make_asset_data, make_enemy_data, make_investigator_data,
    make_location_data,
)


@pytest.fixture(params=["eon_chart_lv1", "eon_chart_lv4"])
def setup(request):
    card_id = request.param
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()

    inv_data = make_investigator_data(intellect=3, agility=4)
    state.card_database[inv_data.id] = inv_data
    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc_a",
    )
    state.investigators["inv1"] = inv
    loc_a = make_location_data(id="loc_a", shroud=2, connections=["loc_b"])
    loc_b = make_location_data(id="loc_b", connections=["loc_a"])
    for ld in (loc_a, loc_b):
        state.card_database[ld.id] = ld
    state.locations["loc_a"] = LocationState(
        location_id="loc_a", card_data=loc_a, clues=2)
    state.locations["loc_b"] = LocationState(
        location_id="loc_b", card_data=loc_b, clues=0)

    state.card_database[card_id] = make_asset_data(
        id=card_id, traits=["item", "relic"], uses={"secretss": 3})
    inst = CardInstance(
        instance_id="inst_eon", card_id=card_id,
        owner_id="inv1", controller_id="inv1",
    )
    inst.uses = {"secretss": 3}  # 数据双 s 键兼容
    state.cards_in_play["inst_eon"] = inst
    inv.play_area.append("inst_eon")

    cls = EonChart if card_id == "eon_chart_lv1" else EonChartLv4
    impl = cls("inst_eon")
    impl.register(bus, "inst_eon")
    bag = ChaosBag(tokens=[ChaosTokenType.ZERO])
    impl.bind_chaos_bag(bag)
    # 进入你的回合
    bus.emit(EventContext(
        game_state=state, event=GameEvent.INVESTIGATOR_TURN_BEGINS,
        investigator_id="inv1",
    ))
    return state, bus, inv, inst, impl, card_id


class TestMoveAction:
    def test_move_to_connected_location(self, setup):
        state, bus, inv, inst, impl, card_id = setup
        actions = ["move"] if card_id == "eon_chart_lv1" else ["move", "investigate"]
        assert impl.activate(state, "inv1", actions=actions) is True
        assert inv.location_id == "loc_b"
        assert inst.exhausted is True
        assert inst.uses["secretss"] == 2

    def test_outside_your_turn_fails(self, setup):
        state, bus, inv, inst, impl, card_id = setup
        bus.emit(EventContext(
            game_state=state, event=GameEvent.INVESTIGATOR_TURN_ENDS,
            investigator_id="inv1",
        ))
        actions = ["move"] if card_id == "eon_chart_lv1" else ["move", "investigate"]
        assert impl.activate(state, "inv1", actions=actions) is False
        assert inst.uses["secretss"] == 3


class TestInvestigateAction:
    def test_investigate_discovers_clue(self, setup):
        """调查（回放智力检定）：成功发现1条线索。"""
        state, bus, inv, inst, impl, card_id = setup
        actions = ["investigate"] if card_id == "eon_chart_lv1" else ["investigate", "move"]
        assert impl.activate(state, "inv1", actions=actions) is True
        # 智力3+0 vs 隐蔽2 → 成功（lv4 顺序 investigate→move，先拿线索再移动）
        assert inv.clues == 1
        assert state.locations["loc_a"].clues == 1


class TestEvadeAction:
    def test_evade_engaged_enemy(self, setup):
        """躲避：成功则敌人横置并解除交战。"""
        state, bus, inv, inst, impl, card_id = setup
        state.card_database["ghoul"] = make_enemy_data(
            id="ghoul", evade=3, health=2)
        enemy = CardInstance(
            instance_id="enemy_1", card_id="ghoul",
            owner_id="scenario", controller_id="scenario",
        )
        state.cards_in_play["enemy_1"] = enemy
        inv.threat_area.append("enemy_1")

        actions = ["evade"] if card_id == "eon_chart_lv1" else ["evade", "move"]
        assert impl.activate(state, "inv1", actions=actions,
                             enemy_instance_id="enemy_1") is True
        # 敏捷4+0 vs 躲避3 → 成功
        assert enemy.exhausted is True
        assert "enemy_1" not in inv.threat_area
        assert "enemy_1" in state.locations["loc_a"].enemies


class TestLv4Validation:
    def test_lv4_requires_two_different_actions(self, setup):
        state, bus, inv, inst, impl, card_id = setup
        if card_id != "eon_chart_lv4":
            pytest.skip("lv4 专属")
        assert impl.activate(state, "inv1", actions=["move"]) is False
        assert impl.activate(state, "inv1",
                             actions=["move", "move"]) is False
        assert inst.uses["secretss"] == 3
