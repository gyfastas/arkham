"""Inquiring Mind (Level 0) — Seeker Skill.
提供3个万能图标。提交限制：你所在地点必须有线索（在提交时检查）。
"""

from backend.cards.base import CardImplementation
from backend.models.enums import TimingPriority  # noqa: F401


class InquiringMind(CardImplementation):
    card_id = "inquiring_mind_lv0"

    # No event handlers needed.
    # This skill card provides 3 wild icons, handled by the commit system.
    # The commit restriction (clue at investigator's location) is
    # enforced by the commit validation logic, not by event handlers.
