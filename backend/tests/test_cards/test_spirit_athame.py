"""Tests for Spirit Athame (Level 1). (03035)

【快速】横置：法术卡检定+2技能值；【行动】横置：攻击+2战斗。
"""

import pytest
from backend.cards.mystic.spirit_athame_lv1 import SpiritAthame
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent, Skill
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, ScenarioState,
)
from backend.tests.conftest import make_asset_data, make_investigator_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()

    inv_data = make_investigator_data(willpower=4, combat=2)
    state.card_database[inv_data.id] = inv_data
    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1",
    )
    state.investigators["inv1"] = inv

    state.card_database["spirit_athame_lv1"] = make_asset_data(
        id="spirit_athame_lv1", name="Spirit Athame", cost=3,
        traits=["item", "relic", "weapon", "melee"],
    )
    state.card_database["shrivelling_lv0"] = make_asset_data(
        id="shrivelling_lv0", name="Shrivelling", traits=["spell"],
    )
    state.card_database["machete_lv0"] = make_asset_data(
        id="machete_lv0", name="Machete", traits=["item", "weapon"],
    )
    for iid, cid in (("inst_shriv", "shrivelling_lv0"),
                     ("inst_mach", "machete_lv0")):
        ci = CardInstance(
            instance_id=iid, card_id=cid, owner_id="inv1", controller_id="inv1",
        )
        state.cards_in_play[iid] = ci
        inv.play_area.append(iid)

    inst = CardInstance(
        instance_id="inst_athame", card_id="spirit_athame_lv1",
        owner_id="inv1", controller_id="inv1",
    )
    state.cards_in_play["inst_athame"] = inst
    inv.play_area.append("inst_athame")

    impl = SpiritAthame("inst_athame")
    impl.register(bus, "inst_athame")
    return state, bus, inv, inst, impl


def _skill_ctx(state, skill, source, amount):
    return EventContext(
        game_state=state, event=GameEvent.SKILL_VALUE_DETERMINED,
        investigator_id="inv1", skill_type=skill, amount=amount, source=source,
    )


class TestSpiritAthameFight:
    def test_fight_armed_gives_plus_2_combat(self, setup):
        """横置武装攻击：以本卡发起的战斗检定+2战斗。"""
        state, bus, inv, inst, impl = setup
        assert impl.activate_fight(state, "inv1") is True
        assert inst.exhausted is True
        ctx = _skill_ctx(state, Skill.COMBAT, "inst_athame", 2)
        bus.emit(ctx)
        assert ctx.amount == 4

    def test_fight_armed_only_for_own_attack(self, setup):
        """武装后其他武器的攻击不加值。"""
        state, bus, inv, inst, impl = setup
        impl.activate_fight(state, "inv1")
        ctx = _skill_ctx(state, Skill.COMBAT, "inst_mach", 2)
        bus.emit(ctx)
        assert ctx.amount == 2

    def test_cannot_fight_while_exhausted(self, setup):
        state, bus, inv, inst, impl = setup
        inst.exhausted = True
        assert impl.activate_fight(state, "inv1") is False


class TestSpiritAthameSpellBoost:
    def test_spell_test_gets_plus_2(self, setup):
        """横置：法术卡（如萎缩术）发起的检定+2技能值。"""
        state, bus, inv, inst, impl = setup
        assert impl.activate_spell_boost(state, "inv1") is True
        ctx = _skill_ctx(state, Skill.COMBAT, "inst_shriv", 2)
        bus.emit(ctx)
        assert ctx.amount == 4

    def test_non_spell_test_not_boosted(self, setup):
        """非法术来源的检定不加值。"""
        state, bus, inv, inst, impl = setup
        impl.activate_spell_boost(state, "inv1")
        ctx = _skill_ctx(state, Skill.COMBAT, "inst_mach", 2)
        bus.emit(ctx)
        assert ctx.amount == 2

    def test_exhaustion_prevents_double_use(self, setup):
        """两个能力都要横置：用过一个另一个当回合不可用。"""
        state, bus, inv, inst, impl = setup
        assert impl.activate_spell_boost(state, "inv1") is True
        assert impl.activate_fight(state, "inv1") is False

    def test_arms_cleared_after_test(self, setup):
        state, bus, inv, inst, impl = setup
        impl.activate_spell_boost(state, "inv1")
        bus.emit(EventContext(
            game_state=state, event=GameEvent.SKILL_TEST_ENDS,
            investigator_id="inv1",
        ))
        inst.exhausted = False
        ctx = _skill_ctx(state, Skill.COMBAT, "inst_shriv", 2)
        bus.emit(ctx)
        assert ctx.amount == 2
