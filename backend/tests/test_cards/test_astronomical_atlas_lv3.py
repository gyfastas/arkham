"""Tests for Astronomical Atlas (Level 3). (08067)

[fast]消耗：牌堆顶非弱点卡叠加到本卡（最多5张）。
[fast]：把叠加卡投入检定；成功则加入手牌而非弃置（每次检定限1张）。
"""

import pytest
from backend.cards.mystic.astronomical_atlas_lv3 import AstronomicalAtlas
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import CardType, GameEvent, PlayerClass
from backend.models.state import (
    CardData, CardInstance, GameState, InvestigatorState, ScenarioState,
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
        deck=["guts_lv0", "perception_lv0"],
    )
    state.investigators["inv1"] = inv
    state.card_database["astronomical_atlas_lv3"] = make_asset_data(
        id="astronomical_atlas_lv3", name="Astronomical Atlas",
        traits=["item", "tome"])
    state.card_database["guts_lv0"] = make_skill_data(
        id="guts_lv0", name="Guts", skill_icons={"willpower": 2})
    state.card_database["perception_lv0"] = make_skill_data(
        id="perception_lv0", name="Perception",
        skill_icons={"intellect": 1})
    # 弱点卡
    state.card_database["weakness_card"] = CardData(
        id="weakness_card", name="Weakness", name_cn="弱点",
        type=CardType.TREACHERY, card_class=PlayerClass.NEUTRAL,
        subtype="basic_weakness",
    )
    inst = CardInstance(
        instance_id="inst_atlas", card_id="astronomical_atlas_lv3",
        owner_id="inv1", controller_id="inv1",
    )
    state.cards_in_play["inst_atlas"] = inst
    inv.play_area.append("inst_atlas")
    impl = AstronomicalAtlas("inst_atlas")
    impl.register(bus, "inst_atlas")
    return state, bus, inv, inst, impl


def _test_ends(state, bus, success):
    ctx = EventContext(
        game_state=state, event=GameEvent.SKILL_TEST_ENDS,
        investigator_id="inv1", success=success,
    )
    bus.emit(ctx)
    return ctx


class TestAstronomicalAtlas:
    def test_attach_top_card(self, setup):
        """消耗：牌堆顶非弱点卡叠加到本卡。"""
        state, bus, inv, inst, impl = setup
        assert impl.attach_top(state, "inv1") is True
        assert inst.exhausted is True
        assert inv.deck == ["perception_lv0"]
        assert impl.attached_cards == ["guts_lv0"]

    def test_weakness_top_stays(self, setup):
        """牌堆顶为弱点：不叠加，留在牌堆。"""
        state, bus, inv, inst, impl = setup
        inv.deck = ["weakness_card", "guts_lv0"]
        assert impl.attach_top(state, "inv1") is False
        assert inv.deck == ["weakness_card", "guts_lv0"]
        assert inst.exhausted is False

    def test_commit_returns_to_hand_on_success(self, setup):
        """叠加卡投入检定成功：加入手牌而非弃置。"""
        state, bus, inv, inst, impl = setup
        impl.attach_top(state, "inv1")
        card_id = impl.commit_attached(state, "inv1", "guts_lv0")
        assert card_id == "guts_lv0"
        assert impl.attached_cards == []
        ctx = _test_ends(state, bus, success=True)
        assert "guts_lv0" in inv.hand
        assert "guts_lv0" not in inv.discard
        assert ctx.extra["astronomical_atlas_returned"] == "guts_lv0"

    def test_commit_discarded_on_failure(self, setup):
        state, bus, inv, inst, impl = setup
        impl.attach_top(state, "inv1")
        impl.commit_attached(state, "inv1", "guts_lv0")
        _test_ends(state, bus, success=False)
        assert "guts_lv0" in inv.discard
        assert "guts_lv0" not in inv.hand

    def test_commit_limit_once_per_test(self, setup):
        state, bus, inv, inst, impl = setup
        inst.exhausted = False
        inv.deck = ["guts_lv0", "perception_lv0"]
        impl.attach_top(state, "inv1")
        impl._attached.append("perception_lv0")  # 模拟已有两张叠加
        first = impl.commit_attached(state, "inv1")
        assert first is not None
        assert impl.commit_attached(state, "inv1") is None  # 限1张

    def test_attach_cap_5(self, setup):
        state, bus, inv, inst, impl = setup
        impl._attached = ["guts_lv0"] * 5
        assert impl.attach_top(state, "inv1") is False

    def test_attachments_discarded_on_leave(self, setup):
        state, bus, inv, inst, impl = setup
        impl.attach_top(state, "inv1")
        bus.emit(EventContext(
            game_state=state, event=GameEvent.CARD_LEAVES_PLAY,
            investigator_id="inv1", target="inst_atlas",
            extra={"card_id": "astronomical_atlas_lv3"},
        ))
        assert "guts_lv0" in inv.discard
        assert impl.attached_cards == []
