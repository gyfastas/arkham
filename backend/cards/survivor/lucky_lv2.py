"""Lucky! (Level 2) — Survivor Event.
运气好！快速。检定失败时+2技能值，然后抽1张牌。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class LuckyLv2(CardImplementation):
    card_id = "lucky_lv2"

    # TODO: Implement fast play when failing skill test
    # +2 skill value, draw 1 card
