"""Seeking Answers (Level 0) — Seeker Event.
调查事件：如果成功，从一个连接地点发现线索（而非你所在地点）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class SeekingAnswers(CardImplementation):
    card_id = "seeking_answers_lv0"

    @on_event(
        GameEvent.SKILL_TEST_SUCCESSFUL,
        priority=TimingPriority.AFTER,
    )
    def discover_clue_at_connecting(self, ctx):
        """If investigation succeeds, discover clue at a connecting location.

        Skeleton — requires complex location targeting to select
        which connecting location to take the clue from.
        """
        if "seeking_answers_lv0" not in ctx.committed_cards:
            return
        if ctx.skill_type != Skill.INTELLECT:
            return
        # TODO: implement connecting location selection and clue transfer
        pass
