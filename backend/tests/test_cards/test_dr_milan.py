"""Tests for Dr. Milan Christopher."""

import pytest

from backend.cards.seeker.dr_milan_christopher_lv0 import DrMilanChristopher
from backend.engine.event_bus import EventContext
from backend.models.enums import GameEvent, Skill
from backend.models.state import CardInstance


@pytest.fixture
def milan(game):
    inv = game.state.get_investigator("test_investigator")
    impl = DrMilanChristopher("milan_1")
    impl.register(game.event_bus, "milan_1")
    inst = CardInstance(
        instance_id="milan_1", card_id="dr_milan_christopher_lv0",
        owner_id="test_investigator", controller_id="test_investigator",
    )
    game.state.cards_in_play["milan_1"] = inst
    inv.play_area.append("milan_1")
    return impl


def _emit(game, event, **kwargs):
    ctx = EventContext(
        game_state=game.state, event=event,
        investigator_id="test_investigator", **kwargs
    )
    game.event_bus.emit(ctx)
    return ctx


class TestDrMilan:
    def test_intellect_bonus(self, game, milan):
        ctx = _emit(game, GameEvent.SKILL_VALUE_DETERMINED,
                    skill_type=Skill.INTELLECT, amount=4)
        assert ctx.amount == 5

    def test_no_bonus_for_other_skills(self, game, milan):
        ctx = _emit(game, GameEvent.SKILL_VALUE_DETERMINED,
                    skill_type=Skill.COMBAT, amount=4)
        assert ctx.amount == 4

    def test_resource_after_successful_investigate(self, game, milan):
        inv = game.state.get_investigator("test_investigator")
        inv.resources = 0

        _emit(game, GameEvent.INVESTIGATE_ACTION_INITIATED)
        ctx = _emit(game, GameEvent.SKILL_TEST_SUCCESSFUL,
                    skill_type=Skill.INTELLECT, success=True)
        assert inv.resources == 1
        assert ctx.extra["dr_milan_resource"] is True

    def test_exhausts_after_reaction_once_per_round(self, game, milan):
        """Taboo errata：反应需消耗米兰（等效每轮限1次）。"""
        inv = game.state.get_investigator("test_investigator")
        inv.resources = 0
        inst = game.state.get_card_instance("milan_1")

        # 第一次成功调查：+1资源并消耗
        _emit(game, GameEvent.INVESTIGATE_ACTION_INITIATED)
        _emit(game, GameEvent.SKILL_TEST_SUCCESSFUL,
              skill_type=Skill.INTELLECT, success=True)
        assert inv.resources == 1
        assert inst.exhausted is True

        # 第二次成功调查：米兰已消耗，不再发资源
        _emit(game, GameEvent.SKILL_TEST_ENDS)
        _emit(game, GameEvent.INVESTIGATE_ACTION_INITIATED)
        _emit(game, GameEvent.SKILL_TEST_SUCCESSFUL,
              skill_type=Skill.INTELLECT, success=True)
        assert inv.resources == 1

        # 就绪后恢复
        inst.exhausted = False
        _emit(game, GameEvent.SKILL_TEST_ENDS)
        _emit(game, GameEvent.INVESTIGATE_ACTION_INITIATED)
        _emit(game, GameEvent.SKILL_TEST_SUCCESSFUL,
              skill_type=Skill.INTELLECT, success=True)
        assert inv.resources == 2

    def test_no_resource_for_non_investigate_intellect_test(self, game, milan):
        """普通智力检定（非调查行动）成功不发资源。"""
        inv = game.state.get_investigator("test_investigator")
        inv.resources = 0

        # 没有 INVESTIGATE_ACTION_INITIATED 标记
        _emit(game, GameEvent.SKILL_TEST_SUCCESSFUL,
              skill_type=Skill.INTELLECT, success=True)
        assert inv.resources == 0

    def test_tracking_cleared_after_test(self, game, milan):
        """检定结束后标记清除，下一轮普通智力检定不发资源。"""
        inv = game.state.get_investigator("test_investigator")
        inv.resources = 0

        _emit(game, GameEvent.INVESTIGATE_ACTION_INITIATED)
        _emit(game, GameEvent.SKILL_TEST_ENDS)
        _emit(game, GameEvent.SKILL_TEST_SUCCESSFUL,
              skill_type=Skill.INTELLECT, success=True)
        assert inv.resources == 0
