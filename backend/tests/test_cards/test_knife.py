"""Tests for Knife (Level 0)."""

import pytest
from backend.cards.neutral.knife_lv0 import Knife
from backend.engine.event_bus import EventBus, EventContext
from backend.engine.skill_test import SkillTestEngine
from backend.models.chaos import ChaosBag
from backend.models.enums import ChaosTokenType, GameEvent, PlayerClass, Skill, SlotType
from backend.models.state import GameState, InvestigatorState, ScenarioState
from backend.tests.conftest import make_investigator_data, make_asset_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()
    bag = ChaosBag()
    bag.seed(42)

    inv_data = make_investigator_data(combat=3)
    state.card_database[inv_data.id] = inv_data

    inv = InvestigatorState(
        investigator_id="inv1",
        card_data=inv_data,
        location_id="loc1",
        deck=["card_a", "card_b"],
    )
    inv.play_area.append("knife_inst")
    state.investigators["inv1"] = inv

    engine = SkillTestEngine(state, bus, bag)

    impl = Knife("knife_inst")
    impl.register(bus, "knife_inst")

    return state, bus, bag, engine, inv, impl


class TestKnife:
    def test_combat_bonus(self, setup):
        state, bus, bag, engine, inv, impl = setup
        bag.tokens = [ChaosTokenType.ZERO]

        result = engine.run_test(
            investigator_id="inv1",
            skill_type=Skill.COMBAT,
            difficulty=4,
            source_instance_id="knife_inst",
        )
        # base 3 + 1 knife bonus + 0 = 4 >= 4
        assert result.success

    def test_no_bonus_for_other_weapons(self, setup):
        """+1 仅限以刀子发起的攻击；徒手/其他武器的战斗不加成。"""
        state, bus, bag, engine, inv, impl = setup
        bag.tokens = [ChaosTokenType.ZERO]

        result = engine.run_test(
            investigator_id="inv1",
            skill_type=Skill.COMBAT,
            difficulty=4,
        )
        # base 3 + 0 = 3 < 4（刀子在场但未以其攻击，无加成）
        assert not result.success

    def test_no_bonus_on_intellect(self, setup):
        state, bus, bag, engine, inv, impl = setup
        bag.tokens = [ChaosTokenType.ZERO]

        result = engine.run_test(
            investigator_id="inv1",
            skill_type=Skill.INTELLECT,
            difficulty=4,
            source_instance_id="knife_inst",
        )
        # base 3 + 0 (no knife bonus for intellect) = 3 < 4
        assert not result.success

    def test_discard_attack(self, setup):
        """[action]弃置刀子：攻击 +2战斗、+1伤害；攻击发起时弃刀。"""
        state, bus, bag, engine, inv, impl = setup
        bag.tokens = [ChaosTokenType.ZERO]

        assert impl.activate_discard_attack(state, "inv1") is True

        # 以刀子发起攻击 → 弃刀（费用）
        bus.emit(EventContext(
            game_state=state, event=GameEvent.FIGHT_ACTION_INITIATED,
            investigator_id="inv1", source="knife_inst",
        ))
        assert "knife_inst" not in inv.play_area
        assert "knife_lv0" in inv.discard

        # +1 伤害（生产流程中 DAMAGE_DEALT 在检定结算（ST.7）时、
        # SKILL_TEST_ENDS 之前触发，故在 on_success 中验证）
        dealt = []

        def _on_success(_result):
            ctx = bus.emit(EventContext(
                game_state=state, event=GameEvent.DAMAGE_DEALT,
                investigator_id="inv1", source="knife_inst", amount=1,
            ))
            dealt.append(ctx.amount)

        result = engine.run_test(
            investigator_id="inv1",
            skill_type=Skill.COMBAT,
            difficulty=5,
            source_instance_id="knife_inst",
            on_success=_on_success,
        )
        # base 3 + 2 discard bonus = 5 >= 5
        assert result.success
        assert dealt == [2]  # 1 基础 + 1 弃刀加成

    def test_normal_attack_no_extra_damage(self, setup):
        """普通（未弃刀）攻击只有+1战斗，无伤害加成。"""
        state, bus, bag, engine, inv, impl = setup
        bag.tokens = [ChaosTokenType.ZERO]

        bus.emit(EventContext(
            game_state=state, event=GameEvent.FIGHT_ACTION_INITIATED,
            investigator_id="inv1", source="knife_inst",
        ))
        assert "knife_inst" in inv.play_area  # 未弃刀

        ctx = bus.emit(EventContext(
            game_state=state, event=GameEvent.DAMAGE_DEALT,
            investigator_id="inv1", source="knife_inst", amount=1,
        ))
        assert ctx.amount == 1

    def test_armed_state_consumed_only_by_knife_fight(self, setup):
        """武装后以其他武器/徒手攻击不消耗弃刀武装，也不弃刀。"""
        state, bus, bag, engine, inv, impl = setup
        assert impl.activate_discard_attack(state, "inv1") is True

        bus.emit(EventContext(
            game_state=state, event=GameEvent.FIGHT_ACTION_INITIATED,
            investigator_id="inv1", source="machete_inst",
        ))
        assert "knife_inst" in inv.play_area
