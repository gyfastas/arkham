"""Cunning Distraction (Level 0) — Survivor Event.
调虎离山。自动闪避你所在地点的所有敌人。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class CunningDistraction(CardImplementation):
    card_id = "cunning_distraction_lv0"

    # TODO: Implement automatic evasion of all enemies at location
