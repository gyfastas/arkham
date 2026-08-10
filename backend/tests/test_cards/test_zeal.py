"""Tests for Zeal (Level 0)."""

import pytest
from backend.cards.survivor.zeal_lv0 import Zeal
from backend.engine.event_bus import EventBus, EventContext
from backend.engine.skill_test import SkillTestEngine
from backend.models.chaos import ChaosBag
from backend.models.enums import ChaosTokenType, GameEvent, Skill
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, LocationState, ScenarioState,
)
from backend.tests.conftest import (
    make_enemy_data, make_investigator_data, make_location_data,
)


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()
    bag = ChaosBag()
    bag.seed(42)

    inv_data = make_investigator_data(combat=3)
    state.card_database[inv_data.id] = inv_data
    enemy_data = make_enemy_data(fight=5)
    state.card_database[enemy_data.id] = enemy_data
    loc_data = make_location_data()
    state.card_database[loc_data.id] = loc_data

    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data,
        location_id="test_location", deck=["deck_a"],
    )
    state.investigators["inv1"] = inv
    state.locations["test_location"] = LocationState(
        location_id="test_location", card_data=loc_data)

    zeal = CardInstance(
        instance_id="zeal_inst", card_id="zeal_lv0",
        owner_id="inv1", controller_id="inv1",
    )
    state.cards_in_play["zeal_inst"] = zeal
    inv.play_area.append("zeal_inst")

    hope = CardInstance(
        instance_id="hope_inst", card_id="hope_lv0",
        owner_id="inv1", controller_id="inv1",
    )
    state.cards_in_play["hope_inst"] = hope
    inv.play_area.append("hope_inst")

    state.cards_in_play["enemy_1"] = CardInstance(
        instance_id="enemy_1", card_id="test_enemy",
        owner_id="scenario", controller_id="scenario",
    )
    inv.threat_area.append("enemy_1")

    engine = SkillTestEngine(state, bus, bag)
    impl = Zeal("zeal_inst")
    impl.register(bus, "zeal_inst")
    return state, bus, bag, engine, inv, impl


class TestZealEntersPlay:
    def test_discards_hope_and_augur(self, setup):
        """强制：热诚入场后丢弃同一拥有者的希望/预见。"""
        state, bus, bag, engine, inv, impl = setup
        bus.emit(EventContext(
            game_state=state, event=GameEvent.CARD_ENTERS_PLAY,
            investigator_id="inv1", target="zeal_inst",
            extra={"card_id": "zeal_lv0"},
        ))
        assert "hope_inst" not in inv.play_area
        assert state.get_card_instance("hope_inst") is None
        assert "hope_lv0" in inv.discard
        # 热诚自己留在场上
        assert "zeal_inst" in inv.play_area


class TestZealFight:
    def test_exhaust_fight_base_combat_5(self, setup):
        """消耗版：以5点基础战斗攻击（3→5，标记照常叠加）。"""
        state, bus, bag, engine, inv, impl = setup
        bag.tokens = [ChaosTokenType.MINUS_1]
        assert impl.activate_fight(state, "inv1", "enemy_1") is True
        zeal = state.get_card_instance("zeal_inst")
        assert zeal.exhausted

        result = engine.run_test(
            investigator_id="inv1", skill_type=Skill.COMBAT,
            difficulty=5, source_instance_id="zeal_inst",
        )
        # 基础设为5：5 - 1 = 4 < 5 → 失败（验证按差值修正而非简单+2）
        assert result.modified_skill == 4
        assert not result.success

    def test_discard_fight_auto_succeeds_and_shuffles(self, setup):
        """丢弃版：自动成功（覆盖自动失败标记）；结算后洗回牌堆。"""
        state, bus, bag, engine, inv, impl = setup
        bag.tokens = [ChaosTokenType.AUTO_FAIL]
        # 希望不在场也不入弃牌堆 → 结算后无放卡
        inv.play_area.remove("hope_inst")
        state.cards_in_play.pop("hope_inst")

        assert impl.activate_fight_discard(state, "inv1", "enemy_1") is True
        assert "zeal_inst" not in inv.play_area
        assert "zeal_lv0" in inv.discard

        result = engine.run_test(
            investigator_id="inv1", skill_type=Skill.COMBAT,
            difficulty=5, source_instance_id="zeal_inst",
        )
        assert result.success
        # 结算后：热诚洗入牌堆；弃牌堆中的希望被放入场
        assert "zeal_lv0" not in inv.discard
        assert "zeal_lv0" in inv.deck
        returned = [
            ci.card_id for ci in state.cards_in_play.values()
            if ci.card_id == "hope_lv0"
        ]
        # 本用例弃牌堆无希望（hope 仍在 play_area 未丢弃）→ 无放卡
        assert returned == []

    def test_discard_fight_brings_back_hope_from_discard(self, setup):
        """丢弃版：弃牌堆中有希望时，结算后将其放入场。"""
        state, bus, bag, engine, inv, impl = setup
        bag.tokens = [ChaosTokenType.AUTO_FAIL]
        # 希望先进入弃牌堆
        inv.play_area.remove("hope_inst")
        state.cards_in_play.pop("hope_inst")
        inv.discard.append("hope_lv0")

        impl.activate_fight_discard(state, "inv1", "enemy_1")
        result = engine.run_test(
            investigator_id="inv1", skill_type=Skill.COMBAT,
            difficulty=5, source_instance_id="zeal_inst",
        )
        assert result.success
        assert "hope_lv0" not in inv.discard
        hope_in_play = [
            iid for iid, ci in state.cards_in_play.items()
            if ci.card_id == "hope_lv0" and iid in inv.play_area
        ]
        assert len(hope_in_play) == 1

    def test_fight_requires_ready(self, setup):
        """热诚已消耗时不能启动。"""
        state, bus, bag, engine, inv, impl = setup
        state.get_card_instance("zeal_inst").exhausted = True
        assert impl.activate_fight(state, "inv1", "enemy_1") is False
