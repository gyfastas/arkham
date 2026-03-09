"""Aquinnah (Level 3) — Survivor Asset, Ally slot.
安奎娜（升级版）。敌人攻击时，疲倦并承受1恐惧：将伤害和恐惧转给另一个敌人。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class AquinnahLv3(CardImplementation):
    card_id = "aquinnah_lv3"

    # TODO: Implement enemy attack redirect — exhaust + 1 horror,
    # redirect damage AND horror to another enemy at your location
