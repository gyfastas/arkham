"""Lucky! (Level 0) — Survivor Event.
运气好！快速。当你即将检定失败时，技能值+2。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class Lucky(CardImplementation):
    card_id = "lucky_lv0"

    # TODO: Implement fast play when failing skill test, +2 skill value
