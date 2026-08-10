"""Tests for Sharp Vision (Level 1)."""

import pytest
from backend.cards.survivor.sharp_vision_lv1 import SharpVision
from backend.engine.event_bus import EventBus, EventContext
from backend.engine.skill_test import SkillTestEngine
from backend.models.chaos import ChaosBag
from backend.models.enums import GameEvent, Skill
from backend.models.state import GameState, InvestigatorState, LocationState, ScenarioState
from backend.tests.conftest import make_investigator_data, make_location_data, make_skill_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()
    bag = ChaosBag()
    bag.seed(42)

    inv_data = make_investigator_data(intellect=3)
    state.card_database[inv_data.id] = inv_data
    state.card_database["sharp_vision_lv1"] = make_skill_data(
        id="sharp_vision_lv1", skill_icons={"intellect": 1})

    loc_data = make_location_data(shroud=2)
    state.card_database[loc_data.id] = loc_data

    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data,
        location_id="test_location", hand=["sharp_vision_lv1"],
    )
    state.investigators["inv1"] = inv
    state.locations["test_location"] = LocationState(
        location_id="test_location", card_data=loc_data, clues=3)

    engine = SkillTestEngine(state, bus, bag)
    impl = SharpVision("sv_inst")
    impl.register(bus, "sv_inst")
    return state, bus, bag, engine, inv


def _investigate(engine, state, bus, inv, difficulty):
    """模拟基础调查：成功时结算基础发现并发 CLUE_DISCOVERED。"""
    loc = state.get_location(inv.location_id)

    def on_success(_result):
        if loc.clues > 0:
            loc.clues -= 1
            inv.clues += 1
            bus.emit(EventContext(
                game_state=state, event=GameEvent.CLUE_DISCOVERED,
                investigator_id=inv.investigator_id,
                location_id=loc.location_id, amount=1,
            ))
    return engine.run_test(
        investigator_id="inv1", skill_type=Skill.INTELLECT,
        difficulty=difficulty, committed_card_ids=["sharp_vision_lv1"],
        on_success=on_success,
    )


class TestSharpVision:
    def test_icons_boosted_on_intellect(self, setup):
        """投入智力检定：印刷1 + 获得2 = 3个图标。"""
        state, bus, bag, engine, inv = setup
        from backend.models.enums import ChaosTokenType
        bag.tokens = [ChaosTokenType.ZERO]
        result = _investigate(engine, state, bus, inv, difficulty=6)
        # base 3 + 3 icons + 0 = 6 >= 6
        assert result.committed_icons == 3
        assert result.success

    def test_no_boost_on_other_skills(self, setup):
        """非智力检定：不加图标。"""
        state, bus, bag, engine, inv = setup
        from backend.models.enums import ChaosTokenType
        bag.tokens = [ChaosTokenType.ZERO]
        result = engine.run_test(
            investigator_id="inv1", skill_type=Skill.COMBAT,
            difficulty=5, committed_card_ids=["sharp_vision_lv1"],
        )
        # 仅印刷的智力图标不计入战斗；万能图标无 → 0
        assert result.committed_icons == 0

    def test_extra_clue_on_success_by_2(self, setup):
        """调查成功且超出2点：基础1 + 额外1 = 2条线索。"""
        state, bus, bag, engine, inv = setup
        from backend.models.enums import ChaosTokenType
        bag.tokens = [ChaosTokenType.ZERO]
        loc = state.get_location("test_location")
        result = _investigate(engine, state, bus, inv, difficulty=4)
        # 3 + 3 + 0 = 6 vs 4 → 超出2点
        assert result.success
        assert inv.clues == 2
        assert loc.clues == 1

    def test_no_extra_clue_below_margin_2(self, setup):
        """成功但只超出1点：无额外线索。"""
        state, bus, bag, engine, inv = setup
        from backend.models.enums import ChaosTokenType
        bag.tokens = [ChaosTokenType.ZERO]
        loc = state.get_location("test_location")
        result = _investigate(engine, state, bus, inv, difficulty=5)
        assert result.success
        assert inv.clues == 1
        assert loc.clues == 2

    def test_no_extra_clue_outside_investigate(self, setup):
        """非调查的智力检定（无基础发现）：即便超出2点也不发线索。"""
        state, bus, bag, engine, inv = setup
        from backend.models.enums import ChaosTokenType
        bag.tokens = [ChaosTokenType.ZERO]
        result = engine.run_test(
            investigator_id="inv1", skill_type=Skill.INTELLECT,
            difficulty=2, committed_card_ids=["sharp_vision_lv1"],
        )
        assert result.success
        assert inv.clues == 0
