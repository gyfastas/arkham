"""Tests for Occult Scraps (Level 0) — weakness asset with willpower penalties."""

from backend.cards.neutral.occult_scraps_lv0 import OccultScraps
from backend.engine.event_bus import EventContext
from backend.models.enums import GameEvent, Skill
from backend.models.state import CardInstance


def _register(game, instance_id="scraps_1"):
    impl = OccultScraps(instance_id)
    impl.register(game.event_bus, instance_id)
    return impl


def _skill_ctx(game, skill, amount=3):
    ctx = EventContext(
        game_state=game.state,
        event=GameEvent.SKILL_VALUE_DETERMINED,
        investigator_id="test_investigator",
        skill_type=skill,
        amount=amount,
    )
    game.event_bus.emit(ctx)
    return ctx


class TestOccultScraps:
    def test_in_hand_willpower_penalty(self, game):
        """在手牌中：意志-2。"""
        _register(game)
        inv = game.state.get_investigator("test_investigator")
        inv.hand.append("occult_scraps_lv0")

        ctx = _skill_ctx(game, Skill.WILLPOWER, amount=3)
        assert ctx.amount == 1  # 3 - 2

    def test_in_play_willpower_penalty(self, game):
        """在场：意志-1。"""
        _register(game)
        inv = game.state.get_investigator("test_investigator")
        ci = CardInstance(
            instance_id="scraps_1", card_id="occult_scraps_lv0",
            owner_id="test_investigator", controller_id="test_investigator",
        )
        game.state.cards_in_play["scraps_1"] = ci
        inv.play_area.append("scraps_1")

        ctx = _skill_ctx(game, Skill.WILLPOWER, amount=3)
        assert ctx.amount == 2  # 3 - 1

    def test_other_skills_unaffected(self, game):
        """其他技能不受影响。"""
        _register(game)
        inv = game.state.get_investigator("test_investigator")
        inv.hand.append("occult_scraps_lv0")

        ctx = _skill_ctx(game, Skill.COMBAT, amount=4)
        assert ctx.amount == 4

    def test_not_held_no_penalty(self, game):
        """既不在手也不在场（其他调查员的卡）：无惩罚。"""
        _register(game)
        ctx = _skill_ctx(game, Skill.WILLPOWER, amount=3)
        assert ctx.amount == 3
