"""Tests for Close the Circle (Level 1). (08062)

充能数=你控制卡牌的不同职阶数（含本卡）。[fast]花1充能+消耗：进行一次
基础行动，期间每次检定可用意志代替指定技能（自动取有利分支）。
"""

import pytest
from backend.cards.mystic.close_the_circle_lv1 import CloseTheCircle
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent, PlayerClass, Skill
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, ScenarioState,
)
from backend.tests.conftest import make_asset_data, make_investigator_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()
    inv_data = make_investigator_data(willpower=5, intellect=5, combat=2)
    state.card_database[inv_data.id] = inv_data
    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1",
    )
    state.investigators["inv1"] = inv
    state.card_database["close_the_circle_lv1"] = make_asset_data(
        id="close_the_circle_lv1", name="Close the Circle",
        traits=["ritual", "synergy"],
    )
    state.card_database["close_the_circle_lv1"].card_class = PlayerClass.MYSTIC
    # 两张不同职阶的其他在场卡
    state.card_database["guardian_card"] = make_asset_data(
        id="guardian_card", name="G", card_class=PlayerClass.GUARDIAN)
    state.card_database["neutral_card"] = make_asset_data(
        id="neutral_card", name="N", card_class=PlayerClass.NEUTRAL)
    for iid, cid in (("inst_g", "guardian_card"), ("inst_n", "neutral_card")):
        state.cards_in_play[iid] = CardInstance(
            instance_id=iid, card_id=cid, owner_id="inv1", controller_id="inv1")
        inv.play_area.append(iid)
    inst = CardInstance(
        instance_id="inst_ctc", card_id="close_the_circle_lv1",
        owner_id="inv1", controller_id="inv1",
    )
    state.cards_in_play["inst_ctc"] = inst
    inv.play_area.append("inst_ctc")
    impl = CloseTheCircle("inst_ctc")
    impl.register(bus, "inst_ctc")
    return state, bus, inv, inst, impl


class TestCloseTheCircle:
    def test_charges_from_class_count(self, setup):
        """入场：充能=职阶数（mystic+guardian+neutral=3）。"""
        state, bus, inv, inst, impl = setup
        bus.emit(EventContext(
            game_state=state, event=GameEvent.CARD_ENTERS_PLAY,
            investigator_id="inv1", target="inst_ctc",
            extra={"card_id": "close_the_circle_lv1"},
        ))
        assert inst.uses["charges"] == 3

    def test_activate_spends_charge_and_exhausts(self, setup):
        state, bus, inv, inst, impl = setup
        inst.uses["charges"] = 2
        assert impl.activate(state, "inv1") is True
        assert inst.uses["charges"] == 1
        assert inst.exhausted is True

    def test_willpower_substitute_when_beneficial(self, setup):
        """行动期间战斗检定：意志(5)>战斗(2)，替换为5。"""
        state, bus, inv, inst, impl = setup
        inst.uses["charges"] = 1
        impl.activate(state, "inv1")
        ctx = EventContext(
            game_state=state, event=GameEvent.SKILL_VALUE_DETERMINED,
            investigator_id="inv1", skill_type=Skill.COMBAT, amount=2,
        )
        bus.emit(ctx)
        assert ctx.amount == 5
        assert ctx.extra["close_the_circle_substituted"] == "combat"

    def test_no_substitute_when_not_beneficial(self, setup):
        """智力(5)不高于意志(5)：不替换。"""
        state, bus, inv, inst, impl = setup
        inst.uses["charges"] = 1
        impl.activate(state, "inv1")
        ctx = EventContext(
            game_state=state, event=GameEvent.SKILL_VALUE_DETERMINED,
            investigator_id="inv1", skill_type=Skill.INTELLECT, amount=5,
        )
        bus.emit(ctx)
        assert ctx.amount == 5
        assert "close_the_circle_substituted" not in ctx.extra

    def test_cleared_after_action(self, setup):
        state, bus, inv, inst, impl = setup
        inst.uses["charges"] = 1
        impl.activate(state, "inv1")
        bus.emit(EventContext(
            game_state=state, event=GameEvent.ACTION_PERFORMED,
            investigator_id="inv1",
        ))
        ctx = EventContext(
            game_state=state, event=GameEvent.SKILL_VALUE_DETERMINED,
            investigator_id="inv1", skill_type=Skill.COMBAT, amount=2,
        )
        bus.emit(ctx)
        assert ctx.amount == 2
