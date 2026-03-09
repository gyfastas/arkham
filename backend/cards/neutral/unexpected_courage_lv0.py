"""Unexpected Courage (Level 0) — Neutral Skill.
绝处逢生。提供2个万能图标，无额外效果。
"""

from backend.cards.base import CardImplementation


class UnexpectedCourage(CardImplementation):
    card_id = "unexpected_courage_lv0"
    # No active abilities — provides 2 wild icons.
