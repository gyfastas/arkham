"""Tests for Ariadne's Twine (Level 3). (07304)

[快速]横置：资产上1秘密换1资源，或1资源换资产上1秘密。
"""

import pytest

from backend.cards.seeker.ariadnes_twine_lv3 import AriadnesTwine
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
        resources=3,
    )
    state.investigators["inv1"] = inv

    state.card_database["ariadnes_twine_lv3"] = make_asset_data(
        id="ariadnes_twine_lv3", traits=["ritual"], uses={"secretss": 0})
    twine = CardInstance(
        instance_id="inst_twine", card_id="ariadnes_twine_lv3",
        owner_id="inv1", controller_id="inv1",
    )
    twine.uses = {"secretss": 0}
    state.cards_in_play["inst_twine"] = twine
    inv.play_area.append("inst_twine")

    state.card_database["stone"] = make_asset_data(
        id="stone", traits=["item", "relic"], uses={"secrets": 2})
    stone = CardInstance(
        instance_id="inst_stone", card_id="stone",
        owner_id="inv1", controller_id="inv1",
    )
    stone.uses = {"secrets": 2}
    state.cards_in_play["inst_stone"] = stone
    inv.play_area.append("inst_stone")

    impl = AriadnesTwine("inst_twine")
    impl.register(bus, "inst_twine")
    return state, bus, inv, twine, stone, impl


class TestAriadnesTwine:
    def test_secret_to_resource_from_other_asset(self, setup):
        """横置：你控制的资产上1秘密转为1资源（本卡无秘密时取其它资产）。"""
        state, bus, inv, twine, stone, impl = setup
        resources_before = inv.resources
        assert impl.activate(state, "inv1") is True
        assert twine.exhausted is True
        assert stone.uses["secrets"] == 1
        assert inv.resources == resources_before + 1

    def test_resource_to_secret_on_twine(self, setup):
        """反向：1资源转为本卡上1秘密（兼容双 s 键）。"""
        state, bus, inv, twine, stone, impl = setup
        resources_before = inv.resources
        assert impl.activate(state, "inv1", direction="to_secret") is True
        assert inv.resources == resources_before - 1
        assert twine.uses["secretss"] == 1

    def test_exhausted_fails(self, setup):
        state, bus, inv, twine, stone, impl = setup
        twine.exhausted = True
        assert impl.activate(state, "inv1") is False

    def test_no_secret_source_fails(self, setup):
        state, bus, inv, twine, stone, impl = setup
        stone.uses["secrets"] = 0
        assert impl.activate(state, "inv1") is False
