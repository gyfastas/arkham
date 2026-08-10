"""Tests for Hawk-Eye Folding Camera (Level 0)."""

import pytest
from backend.cards.seeker.hawk_eye_folding_camera_lv0 import HawkEyeFoldingCamera
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent, Skill
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, LocationState, ScenarioState,
)
from backend.tests.conftest import make_investigator_data, make_location_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()

    inv_data = make_investigator_data(willpower=2, intellect=3, sanity=5)
    state.card_database[inv_data.id] = inv_data
    for loc_id in ("loc_a", "loc_b", "loc_c"):
        loc_data = make_location_data(id=loc_id)
        state.card_database[loc_id] = loc_data
        state.locations[loc_id] = LocationState(
            location_id=loc_id, card_data=loc_data, clues=0, revealed=True,
        )

    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc_a",
    )
    state.investigators["inv1"] = inv

    inst = CardInstance(
        instance_id="cam_1", card_id="hawk_eye_folding_camera_lv0",
        owner_id="inv1", controller_id="inv1",
    )
    state.cards_in_play["cam_1"] = inst
    inv.play_area.append("cam_1")

    impl = HawkEyeFoldingCamera("cam_1")
    impl.register(bus, "cam_1")
    return state, bus, inv, inst, impl


def _last_clue(state, bus, loc_id):
    """模拟：你所在地点最后1个线索被发现（发现后地点线索为0）。"""
    inv = state.get_investigator("inv1")
    inv.location_id = loc_id
    ctx = EventContext(
        game_state=state, event=GameEvent.CLUE_DISCOVERED,
        investigator_id="inv1", location_id=loc_id, amount=1,
    )
    bus.emit(ctx)
    return ctx


def _skill_ctx(state, bus, skill, base):
    ctx = EventContext(
        game_state=state, event=GameEvent.SKILL_VALUE_DETERMINED,
        investigator_id="inv1", skill_type=skill, amount=base,
    )
    bus.emit(ctx)
    return ctx


class TestHawkEyeFoldingCamera:
    def test_evidence_and_willpower_bonus(self, setup):
        """地点线索归零：放置1个证据；≥1证据 +1意志。"""
        state, bus, inv, inst, impl = setup
        ctx = _last_clue(state, bus, "loc_a")
        assert ctx.extra["hawk_eye_evidence"] == 1
        assert inst.uses["evidence"] == 1

        assert _skill_ctx(state, bus, Skill.WILLPOWER, 2).amount == 3
        # 1个证据尚无智力加值
        assert _skill_ctx(state, bus, Skill.INTELLECT, 3).amount == 3

    def test_intellect_bonus_at_two_evidence(self, setup):
        """≥2证据 +1智力（另一地点再次触发）。"""
        state, bus, inv, inst, impl = setup
        _last_clue(state, bus, "loc_a")
        ctx = _last_clue(state, bus, "loc_b")
        assert ctx.extra["hawk_eye_evidence"] == 2
        assert _skill_ctx(state, bus, Skill.INTELLECT, 3).amount == 4

    def test_sanity_bonus_at_three_evidence(self, setup):
        """≥3证据 +1神智值；离场回收。"""
        state, bus, inv, inst, impl = setup
        _last_clue(state, bus, "loc_a")
        _last_clue(state, bus, "loc_b")
        sanity_before = inv.sanity
        _last_clue(state, bus, "loc_c")
        assert inst.uses["evidence"] == 3
        assert inv.sanity == sanity_before + 1

        # 离场时回收
        bus.emit(EventContext(
            game_state=state, event=GameEvent.CARD_LEAVES_PLAY,
            investigator_id="inv1", target="cam_1",
        ))
        assert inv.sanity == sanity_before

    def test_once_per_location_per_game(self, setup):
        """同一地点每场游戏只触发一次。"""
        state, bus, inv, inst, impl = setup
        _last_clue(state, bus, "loc_a")
        ctx = _last_clue(state, bus, "loc_a")
        assert "hawk_eye_evidence" not in ctx.extra
        assert inst.uses["evidence"] == 1

    def test_no_trigger_while_clues_remain(self, setup):
        """地点还有线索时不触发。"""
        state, bus, inv, inst, impl = setup
        state.locations["loc_a"].clues = 1
        ctx = _last_clue(state, bus, "loc_a")
        assert "hawk_eye_evidence" not in ctx.extra
        assert inst.uses.get("evidence", 0) == 0
