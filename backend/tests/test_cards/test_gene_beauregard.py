"""Tests for Gené Beauregard (Level 3)."""

import pytest
from backend.cards.seeker.gené_beauregard_lv3 import GeneBeauregard
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import Action, GameEvent, Skill
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, LocationState, ScenarioState,
)
from backend.tests.conftest import make_investigator_data, make_location_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()

    inv_data = make_investigator_data(intellect=3, agility=2)
    state.card_database[inv_data.id] = inv_data
    loc_a = make_location_data(id="loc_a", connections=["loc_b"])
    loc_b = make_location_data(id="loc_b", connections=["loc_a"])
    state.card_database["loc_a"] = loc_a
    state.card_database["loc_b"] = loc_b
    state.locations["loc_a"] = LocationState(
        location_id="loc_a", card_data=loc_a, clues=2, revealed=True,
    )
    state.locations["loc_b"] = LocationState(
        location_id="loc_b", card_data=loc_b, clues=0, revealed=True,
    )

    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc_a",
    )
    state.investigators["inv1"] = inv

    inst = CardInstance(
        instance_id="gene_1", card_id="gené_beauregard_lv3",
        owner_id="inv1", controller_id="inv1",
    )
    state.cards_in_play["gene_1"] = inst
    inv.play_area.append("gene_1")

    impl = GeneBeauregard("gene_1")
    impl.register(bus, "gene_1")
    return state, bus, inv, inst, impl


def _emit(state, bus, event, **kwargs):
    ctx = EventContext(game_state=state, event=event, investigator_id="inv1", **kwargs)
    bus.emit(ctx)
    return ctx


class TestGeneBeauregard:
    def test_constant_skill_bonuses(self, setup):
        """常驻 +1 智力 / +1 敏捷。"""
        state, bus, inv, inst, impl = setup
        ctx = _emit(state, bus, GameEvent.SKILL_VALUE_DETERMINED,
                    skill_type=Skill.INTELLECT, amount=3)
        assert ctx.amount == 4
        ctx = _emit(state, bus, GameEvent.SKILL_VALUE_DETERMINED,
                    skill_type=Skill.AGILITY, amount=2)
        assert ctx.amount == 3
        # 其它技能无加值
        ctx = _emit(state, bus, GameEvent.SKILL_VALUE_DETERMINED,
                    skill_type=Skill.COMBAT, amount=3)
        assert ctx.amount == 3

    def test_reaction_pulls_clue_after_move(self, setup):
        """你的回合移动后：自动把连接地点的1个线索移到你所在地点。"""
        state, bus, inv, inst, impl = setup
        loc_a = state.locations["loc_a"]
        loc_b = state.locations["loc_b"]

        _emit(state, bus, GameEvent.INVESTIGATOR_TURN_BEGINS)
        inv.location_id = "loc_b"  # 引擎移动已生效
        ctx = _emit(state, bus, GameEvent.ACTION_PERFORMED, action=Action.MOVE)

        assert ctx.extra.get("gene_beauregard_triggered") is True
        assert loc_a.clues == 1  # 连接地点 2 - 1
        assert loc_b.clues == 1  # 你所在地点 0 + 1
        assert inst.exhausted is True

    def test_no_reaction_outside_your_turn(self, setup):
        """不在你的回合：移动后不触发。"""
        state, bus, inv, inst, impl = setup
        _emit(state, bus, GameEvent.INVESTIGATOR_TURN_BEGINS)
        _emit(state, bus, GameEvent.INVESTIGATOR_TURN_ENDS)
        ctx = _emit(state, bus, GameEvent.ACTION_PERFORMED, action=Action.MOVE)
        assert "gene_beauregard_triggered" not in ctx.extra
        assert inst.exhausted is False

    def test_relocate_enemy_away(self, setup):
        """公开方法：将你所在地点的非精英敌人移到连接地点。"""
        from backend.tests.conftest import make_enemy_data
        state, bus, inv, inst, impl = setup
        enemy_data = make_enemy_data()
        state.card_database["test_enemy"] = enemy_data
        enemy = CardInstance(
            instance_id="e1", card_id="test_enemy",
            owner_id="scenario", controller_id="scenario",
        )
        state.cards_in_play["e1"] = enemy
        inv.threat_area.append("e1")

        ok = impl.relocate(state, "inv1", kind="enemy_away", location_id="loc_b")
        assert ok is True
        assert "e1" not in inv.threat_area
        assert "e1" in state.locations["loc_b"].enemies
        assert inst.exhausted is True
