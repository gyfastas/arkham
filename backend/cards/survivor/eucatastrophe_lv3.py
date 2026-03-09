"""Eucatastrophe (Level 3) — Survivor Event.
美满结局。快速。取消将技能值降为0的混沌标记，视为远古印记。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class Eucatastrophe(CardImplementation):
    card_id = "eucatastrophe_lv3"

    # TODO: Implement fast cancel of chaos token that reduces skill to 0
    # treat as elder sign instead
