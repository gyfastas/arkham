"""Tests for Archaic Glyphs (Level 0).

官方：[行动]弃1张含智力图标的手牌：放置1个秘密。
强制 - 第3个秘密放置后：丢弃古代雕文，获得5资源，冒险日志记录"你翻译出了雕文"。
"""

import pytest

from backend.cards.seeker.archaic_glyphs_lv0 import (
    CAMPAIGN_LOG_ENTRY, ArchaicGlyphs,
)
from backend.engine.event_bus import EventBus
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, ScenarioState,
)
from backend.tests.conftest import (
    make_asset_data, make_investigator_data, make_skill_data,
)


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()

    inv_data = make_investigator_data()
    state.card_database[inv_data.id] = inv_data
    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1",
        resources=0,
    )
    inv.hand = ["perception_lv0", "guts_lv0", "machete_lv0"]
    state.investigators["inv1"] = inv

    state.card_database["archaic_glyphs_lv0"] = make_asset_data(
        id="archaic_glyphs_lv0", name="Archaic Glyphs", cost=0,
        traits=["item", "occult", "tome"],
    )
    state.card_database["perception_lv0"] = make_skill_data(
        id="perception_lv0", skill_icons={"intellect": 2})
    state.card_database["guts_lv0"] = make_skill_data(
        id="guts_lv0", skill_icons={"willpower": 2})
    state.card_database["machete_lv0"] = make_asset_data(
        id="machete_lv0", name="Machete")  # 无技能图标

    inst = CardInstance(
        instance_id="inst_glyphs", card_id="archaic_glyphs_lv0",
        owner_id="inv1", controller_id="inv1",
    )
    state.cards_in_play["inst_glyphs"] = inst
    inv.play_area.append("inst_glyphs")

    impl = ArchaicGlyphs("inst_glyphs")
    impl.register(bus, "inst_glyphs")
    return state, bus, inv, inst, impl


class TestArchaicGlyphs:
    def test_activate_discards_intellect_card_and_places_secret(self, setup):
        """自动弃第一张含智力图标的牌（perception），放置1秘密。"""
        state, bus, inv, inst, impl = setup
        assert impl.activate(state, "inv1") is True
        assert inst.uses["secrets"] == 1
        assert "perception_lv0" in inv.discard
        assert "perception_lv0" not in inv.hand

    def test_explicit_card_must_have_intellect_icon(self, setup):
        state, bus, inv, inst, impl = setup
        # machete 无智力图标
        assert impl.activate(state, "inv1", card_id="machete_lv0") is False
        assert inst.uses.get("secrets", 0) == 0
        assert "machete_lv0" in inv.hand
        # guts 仅意志图标也不行
        assert impl.activate(state, "inv1", card_id="guts_lv0") is False

    def test_third_secret_discards_and_grants_5_resources(self, setup):
        """第3个秘密：丢弃雕文、+5资源、记录冒险日志。"""
        state, bus, inv, inst, impl = setup
        inv.hand = ["perception_lv0", "perception_lv0", "perception_lv0"]
        for _ in range(3):
            assert impl.activate(state, "inv1") is True

        assert "inst_glyphs" not in inv.play_area
        assert "inst_glyphs" not in state.cards_in_play
        assert "archaic_glyphs_lv0" in inv.discard
        assert inv.resources == 5
        assert CAMPAIGN_LOG_ENTRY in state.scenario.vars["campaign_log"]

    def test_no_intellect_card_in_hand_fails(self, setup):
        state, bus, inv, inst, impl = setup
        inv.hand = ["machete_lv0"]
        assert impl.activate(state, "inv1") is False
