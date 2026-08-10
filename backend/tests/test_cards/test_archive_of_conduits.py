"""Tests for Archive of Conduits (Level 0 & 4). (08033 / 08044)

lv0：打出额外费用放4条地线；成功调查带地线地点后横置收集；集齐4条丢弃换资源。
lv4：使用(4地线)；[快速]移动地线给调查员；[行动]抽牌+治疗。
"""

import pytest

from backend.cards.seeker.archive_of_conduits_lv0 import (
    CAMPAIGN_LOG_ENTRY, ArchiveOfConduits, leyline_store,
)
from backend.cards.seeker.archive_of_conduits_lv4 import ArchiveOfConduitsLv4
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent, Skill
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, LocationState, ScenarioState,
)
from backend.tests.conftest import (
    make_asset_data, make_investigator_data, make_location_data,
)


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()

    inv_data = make_investigator_data()
    state.card_database[inv_data.id] = inv_data
    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc_b",
        resources=0,
    )
    inv.deck = ["c1", "c2", "c3", "c4"]
    state.investigators["inv1"] = inv
    for loc_id in ("loc_a", "loc_b", "loc_c", "loc_d"):
        loc_data = make_location_data(id=loc_id)
        state.card_database[loc_id] = loc_data
        state.locations[loc_id] = LocationState(
            location_id=loc_id, card_data=loc_data, clues=2)

    state.card_database["archive_of_conduits_lv0"] = make_asset_data(
        id="archive_of_conduits_lv0", traits=["item", "tome", "occult"])
    inst = CardInstance(
        instance_id="inst_archive", card_id="archive_of_conduits_lv0",
        owner_id="inv1", controller_id="inv1",
    )
    state.cards_in_play["inst_archive"] = inst
    inv.play_area.append("inst_archive")

    impl = ArchiveOfConduits("inst_archive")
    impl.register(bus, "inst_archive")
    return state, bus, inv, inst, impl


def _enter_play(state, bus, inst):
    bus.emit(EventContext(
        game_state=state, event=GameEvent.CARD_ENTERS_PLAY,
        investigator_id="inv1", target=inst.instance_id,
    ))


def _successful_investigate(state, bus, loc_id):
    bus.emit(EventContext(
        game_state=state, event=GameEvent.INVESTIGATE_ACTION_INITIATED,
        investigator_id="inv1", location_id=loc_id,
    ))
    bus.emit(EventContext(
        game_state=state, event=GameEvent.SKILL_TEST_SUCCESSFUL,
        investigator_id="inv1", skill_type=Skill.INTELLECT,
    ))
    bus.emit(EventContext(
        game_state=state, event=GameEvent.SKILL_TEST_ENDS,
        investigator_id="inv1",
    ))


class TestArchiveLv0:
    def test_enter_play_places_4_leylines(self, setup):
        state, bus, inv, inst, impl = setup
        _enter_play(state, bus, inst)
        locs = leyline_store(state)["locations"]
        assert sum(locs.values()) == 4
        assert len(locs) == 4  # 4个不同地点

    def test_successful_investigate_collects_leyline(self, setup):
        """成功调查带地线地点：横置，地线移到本支援。"""
        state, bus, inv, inst, impl = setup
        _enter_play(state, bus, inst)
        _successful_investigate(state, bus, "loc_b")
        assert inst.exhausted is True
        assert inst.uses["leylines"] == 1
        assert leyline_store(state)["locations"]["loc_b"] == 0

    def test_fourth_leyline_discards_and_grants_resources(self, setup):
        """集齐4条：丢弃本支援、+4资源、记录冒险日志。"""
        state, bus, inv, inst, impl = setup
        _enter_play(state, bus, inst)
        for loc_id in ("loc_a", "loc_b", "loc_c", "loc_d"):
            inst.exhausted = False
            _successful_investigate(state, bus, loc_id)
        assert "inst_archive" not in inv.play_area
        assert "archive_of_conduits_lv0" in inv.discard
        assert inv.resources == 4
        assert CAMPAIGN_LOG_ENTRY in state.scenario.vars["campaign_log"]


class TestArchiveLv4:
    @pytest.fixture
    def setup4(self, setup):
        state, bus, inv, _, _ = setup
        state.card_database["archive_of_conduits_lv4"] = make_asset_data(
            id="archive_of_conduits_lv4", traits=["ritual"],
            uses={"leyliness": 4})  # 数据双 s 键兼容
        inst = CardInstance(
            instance_id="inst_archive4", card_id="archive_of_conduits_lv4",
            owner_id="inv1", controller_id="inv1",
        )
        inst.uses = {"leyliness": 4}
        state.cards_in_play["inst_archive4"] = inst
        inv.play_area.append("inst_archive4")
        impl = ArchiveOfConduitsLv4("inst_archive4")
        impl.register(bus, "inst_archive4")
        _enter_play(state, bus, inst)
        return state, bus, inv, inst, impl

    def test_enter_play_normalizes_uses(self, setup4):
        _, _, _, inst, _ = setup4
        assert inst.uses.get("leylines") == 4
        assert "leyliness" not in inst.uses

    def test_move_leyline_to_investigator(self, setup4):
        state, bus, inv, inst, impl = setup4
        assert impl.activate_move(state, "inv1") is True
        assert inst.uses["leylines"] == 3
        store = leyline_store(state)["investigators"]
        assert store["inv1"] == 1

    def test_channel_draws_and_heals(self, setup4):
        """[行动]带地线调查员：抽1并治疗1伤害。"""
        state, bus, inv, inst, impl = setup4
        inv.damage = 2
        impl.activate_move(state, "inv1")
        hand_before = len(inv.hand)
        assert impl.activate(state, "inv1") is True
        assert len(inv.hand) == hand_before + 1
        assert inv.damage == 1
        # 未移除地线：仍可再次使用
        assert leyline_store(state)["investigators"]["inv1"] == 1

    def test_channel_remove_leyline_double_effect(self, setup4):
        """移除地线：抽2并治疗2。"""
        state, bus, inv, inst, impl = setup4
        inv.horror = 2
        impl.activate_move(state, "inv1")
        hand_before = len(inv.hand)
        assert impl.activate(state, "inv1", remove_leyline=True,
                             heal_kind="horror") is True
        assert len(inv.hand) == hand_before + 2
        assert inv.horror == 0
        assert leyline_store(state)["investigators"]["inv1"] == 0
        # 地线已移除：再次使用失败
        assert impl.activate(state, "inv1") is False
