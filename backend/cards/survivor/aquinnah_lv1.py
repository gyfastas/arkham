"""Aquinnah (Level 1) — Survivor Asset, Ally slot.
安奎娜。敌人攻击时，疲倦并承受1恐惧：将伤害转给另一个敌人。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class AquinnahLv1(CardImplementation):
    card_id = "aquinnah_lv1"

    # TODO: Implement enemy attack redirect — exhaust + 1 horror,
    # redirect damage to another enemy at your location
