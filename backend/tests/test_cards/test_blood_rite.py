"""Tests for Blood-Rite (Level 0). (05317)

抽2张牌，弃至多2张手牌，每张换1资源或花1资源对同地点敌人造成1伤害。
"""

import pytest

from backend.cards.seeker.blood_rite_lv0 import BloodRite
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, LocationState, ScenarioState,
)
from backend.tests.conftest import (
    make_enemy_data, make_event_data, make_investigator_data,
    make_location_data, make_skill_data,
)


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()

    inv_data = make_investigator_data()
    state.card_database[inv_data.id] = inv_data
    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1",
        resources=1,
    )
    for cid in ("h1", "h2"):
        state.card_database[cid] = make_skill_data(id=cid, name=cid)
    inv.hand = ["h1", "h2"]
    inv.deck = ["d1", "d2", "d3"]
    state.investigators["inv1"] = inv

    loc_data = make_location_data(id="loc1")
    state.card_database[loc_data.id] = loc_data
    state.locations["loc1"] = LocationState(
        location_id="loc1", card_data=loc_data, clues=0)

    state.card_database["blood_rite_lv0"] = make_event_data(
        id="blood_rite_lv0", name="Blood-Rite")

    impl = BloodRite("inst_br")
    impl.register(bus, "inst_br")
    return state, bus, inv, impl


def _play(state, bus, **extra):
    ctx = EventContext(
        game_state=state, event=GameEvent.CARD_PLAYED,
        investigator_id="inv1", extra={"card_id": "blood_rite_lv0", **extra},
    )
    bus.emit(ctx)
    return ctx


class TestBloodRite:
    def test_draw2_discard2_gain2(self, setup):
        """自动简化：抽2张，弃手牌前2张，各换1资源。"""
        state, bus, inv, impl = setup
        ctx = _play(state, bus)
        assert "d1" in inv.hand and "d2" in inv.hand
        assert "h1" in inv.discard and "h2" in inv.discard
        assert inv.resources == 1 + 2
        assert ctx.extra["blood_rite_gained"] == 2

    def test_damage_mode_spends_resource_and_damages_enemy(self, setup):
        """显式选择：花1资源对同地点敌人造成1伤害。"""
        state, bus, inv, impl = setup
        state.card_database["ghoul"] = make_enemy_data(id="ghoul", health=2)
        enemy = CardInstance(
            instance_id="enemy_1", card_id="ghoul",
            owner_id="scenario", controller_id="scenario",
        )
        state.cards_in_play["enemy_1"] = enemy
        state.locations["loc1"].enemies.append("enemy_1")

        ctx = _play(
            state, bus,
            blood_rite_choices=[
                {"card_id": "h1", "mode": "damage", "enemy": "enemy_1"},
            ],
        )
        assert enemy.damage == 1
        assert inv.resources == 0  # 1 - 1（伤害模式花费）
        assert ctx.extra["blood_rite_dealt"] == 1
        # 只弃了指定的1张（"至多2张"）
        assert "h2" in inv.hand or "h2" in inv.discard
