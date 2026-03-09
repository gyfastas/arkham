"""Stray Cat (Level 0) — Survivor Asset, Ally slot.
野猫。弃置：自动闪避一个非精英敌人。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class StrayCat(CardImplementation):
    card_id = "stray_cat_lv0"

    # TODO: Implement discard ability to automatically evade non-Elite enemy
