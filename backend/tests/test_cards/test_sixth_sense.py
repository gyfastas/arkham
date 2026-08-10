"""Tests for Sixth Sense (lv0 / lv4)."""

import pytest

from backend.cards.mystic.sixth_sense_lv0 import SixthSense
from backend.cards.mystic.sixth_sense_lv4 import SixthSenseLv4
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import ChaosTokenType, GameEvent, Skill
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, LocationState, ScenarioState,
)
from backend.tests.conftest import (
    make_asset_data, make_investigator_data, make_location_data,
)


def _setup(impl_cls, card_id, willpower=5, intellect=2):
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()

    inv_data = make_investigator_data(willpower=willpower, intellect=intellect)
    state.card_database[inv_data.id] = inv_data
    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1")
    state.investigators["inv1"] = inv

    # loc1（所在，隐藏值4）— loc2（连接，隐藏值2，已揭示）— loc3（二级连接，隐藏值1，已揭示）
    locs = {
        "loc1": make_location_data(id="loc1", shroud=4, connections=["loc2"]),
        "loc2": make_location_data(id="loc2", shroud=2, connections=["loc1", "loc3"]),
        "loc3": make_location_data(id="loc3", shroud=1, connections=["loc2"]),
    }
    for loc_id, cd in locs.items():
        state.card_database[loc_id] = cd
        state.locations[loc_id] = LocationState(
            location_id=loc_id, card_data=cd, clues=2, revealed=True)

    state.card_database[card_id] = make_asset_data(id=card_id)
    inst = CardInstance(
        instance_id="inst1", card_id=card_id,
        owner_id="inv1", controller_id="inv1",
    )
    state.cards_in_play["inst1"] = inst
    inv.play_area.append("inst1")

    impl = impl_cls("inst1")
    impl.register(bus, "inst1")
    return state, bus, inv, inst, impl


def _emit(bus, state, event, **kwargs):
    ctx = EventContext(game_state=state, event=event, investigator_id="inv1", **kwargs)
    bus.emit(ctx)
    return ctx


class TestSixthSenseLv0:
    CID = "sixth_sense_lv0"

    def test_willpower_substitute(self):
        state, bus, inv, inst, impl = _setup(SixthSense, self.CID)
        assert impl.activate(state, "inv1") is True
        ctx = _emit(bus, state, GameEvent.SKILL_VALUE_DETERMINED,
                    skill_type=Skill.INTELLECT, amount=2, difficulty=4)
        assert ctx.amount == 5  # 意志代替智力

    def test_symbol_uses_connected_shroud(self):
        """符号标记：可用连接地点的低隐藏值（等效技能加值 4-2=2）。"""
        state, bus, inv, inst, impl = _setup(SixthSense, self.CID)
        impl.activate(state, "inv1")
        _emit(bus, state, GameEvent.CHAOS_TOKEN_RESOLVED,
              chaos_token=ChaosTokenType.SKULL, skill_type=Skill.INTELLECT)
        ctx = _emit(bus, state, GameEvent.SKILL_VALUE_DETERMINED,
                    skill_type=Skill.INTELLECT, amount=2, difficulty=4)
        assert ctx.amount == 7  # 5 + (4-2)
        assert ctx.extra["sixth_sense_lv0_shroud_used"] == 2
        # 目标应为 loc2（1条连接），不是 loc3
        target = impl._choose_location(state, inv)
        assert target.location_id == "loc2"

    def test_clue_redirected_to_connected_location(self):
        """成功后线索改从连接地点获取（本地点回滚）。"""
        state, bus, inv, inst, impl = _setup(SixthSense, self.CID)
        impl.activate(state, "inv1")
        _emit(bus, state, GameEvent.CHAOS_TOKEN_RESOLVED,
              chaos_token=ChaosTokenType.TABLET, skill_type=Skill.INTELLECT)
        # 模拟引擎成功拾取：本地点-1，调查员+1
        state.locations["loc1"].clues -= 1
        inv.clues += 1
        ctx = _emit(bus, state, GameEvent.CLUE_DISCOVERED, location_id="loc1")
        assert state.locations["loc1"].clues == 2  # 回滚
        assert state.locations["loc2"].clues == 1  # 改从 loc2 发现
        assert inv.clues == 1
        assert ctx.extra["sixth_sense_lv0_redirected"] == "loc2"

    def test_no_symbol_normal_investigation(self):
        state, bus, inv, inst, impl = _setup(SixthSense, self.CID)
        impl.activate(state, "inv1")
        state.locations["loc1"].clues -= 1
        inv.clues += 1
        _emit(bus, state, GameEvent.CLUE_DISCOVERED, location_id="loc1")
        assert state.locations["loc1"].clues == 1  # 不回滚
        assert state.locations["loc2"].clues == 2


class TestSixthSenseLv4:
    CID = "sixth_sense_lv4"

    def test_willpower_plus_two(self):
        state, bus, inv, inst, impl = _setup(SixthSenseLv4, self.CID)
        impl.activate(state, "inv1")
        ctx = _emit(bus, state, GameEvent.SKILL_VALUE_DETERMINED,
                    skill_type=Skill.INTELLECT, amount=2, difficulty=4)
        assert ctx.amount == 7  # 5意志 + 2

    def test_symbol_reaches_two_connections(self):
        """lv4 可选2条连接外的 loc3（隐藏值1）。"""
        state, bus, inv, inst, impl = _setup(SixthSenseLv4, self.CID)
        impl.activate(state, "inv1")
        _emit(bus, state, GameEvent.CHAOS_TOKEN_RESOLVED,
              chaos_token=ChaosTokenType.ELDER_THING, skill_type=Skill.INTELLECT)
        target = impl._choose_location(state, inv)
        assert target.location_id == "loc3"
        ctx = _emit(bus, state, GameEvent.SKILL_VALUE_DETERMINED,
                    skill_type=Skill.INTELLECT, amount=2, difficulty=4)
        assert ctx.amount == 10  # 5 + 2 + (4-1)

    def test_clue_discovered_at_both_locations(self):
        """lv4 "同时"调查：本地点线索保留，目标地点额外发现1个。"""
        state, bus, inv, inst, impl = _setup(SixthSenseLv4, self.CID)
        impl.activate(state, "inv1")
        _emit(bus, state, GameEvent.CHAOS_TOKEN_RESOLVED,
              chaos_token=ChaosTokenType.CULTIST, skill_type=Skill.INTELLECT)
        # 引擎成功拾取本地点线索
        state.locations["loc1"].clues -= 1
        inv.clues += 1
        ctx = _emit(bus, state, GameEvent.CLUE_DISCOVERED, location_id="loc1")
        assert state.locations["loc1"].clues == 1  # 不回滚
        assert state.locations["loc3"].clues == 1  # 额外从 loc3 发现
        assert inv.clues == 2
        assert ctx.extra["sixth_sense_lv4_extra_clue"] == "loc3"
