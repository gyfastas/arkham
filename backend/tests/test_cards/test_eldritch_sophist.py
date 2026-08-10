"""Tests for Eldritch Sophist (Level 0). (07111)

[快速]横置：把你控制的一张资产上的1个秘密/充能移到同地点另一张资产上。
"""

import pytest

from backend.cards.seeker.eldritch_sophist_lv0 import EldritchSophist
from backend.engine.event_bus import EventBus
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, ScenarioState,
)
from backend.tests.conftest import make_asset_data, make_investigator_data


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

    state.card_database["eldritch_sophist_lv0"] = make_asset_data(
        id="eldritch_sophist_lv0", traits=["ally", "miskatonic"],
        uses={"secretss": 3})
    sophist = CardInstance(
        instance_id="inst_sophist", card_id="eldritch_sophist_lv0",
        owner_id="inv1", controller_id="inv1",
    )
    sophist.uses = {"secretss": 3}  # 数据双 s 键兼容
    state.cards_in_play["inst_sophist"] = sophist
    inv.play_area.append("inst_sophist")

    state.card_database["stone"] = make_asset_data(
        id="stone", traits=["item", "relic"], uses={"secrets": 0})
    stone = CardInstance(
        instance_id="inst_stone", card_id="stone",
        owner_id="inv1", controller_id="inv1",
    )
    stone.uses = {"secrets": 0}
    state.cards_in_play["inst_stone"] = stone
    inv.play_area.append("inst_stone")

    impl = EldritchSophist("inst_sophist")
    impl.register(bus, "inst_sophist")
    return state, bus, inv, sophist, stone, impl


class TestEldritchSophist:
    def test_move_secret_default(self, setup):
        """缺省：本卡（有秘密）为来源，第一张其它资产为目标。"""
        state, bus, inv, sophist, stone, impl = setup
        assert impl.activate(state, "inv1") is True
        assert sophist.exhausted is True
        assert sophist.uses["secretss"] == 2
        assert stone.uses["secrets"] == 1

    def test_move_charge_explicit(self, setup):
        """显式指定来源/目标/类型：移动1个充能。"""
        state, bus, inv, sophist, stone, impl = setup
        state.card_database["wand"] = make_asset_data(
            id="wand", uses={"charges": 2})
        wand = CardInstance(
            instance_id="inst_wand", card_id="wand",
            owner_id="inv1", controller_id="inv1",
        )
        wand.uses = {"charges": 2}
        state.cards_in_play["inst_wand"] = wand
        inv.play_area.append("inst_wand")

        assert impl.activate(state, "inv1",
                             source_instance_id="inst_wand",
                             target_instance_id="inst_stone",
                             token_type="charges") is True
        assert wand.uses["charges"] == 1
        assert stone.uses["charges"] == 1

    def test_exhausted_fails(self, setup):
        state, bus, inv, sophist, stone, impl = setup
        sophist.exhausted = True
        assert impl.activate(state, "inv1") is False
