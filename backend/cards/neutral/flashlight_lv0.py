"""Flashlight (Level 0) — Neutral Asset, Hand slot.
手电筒。Uses (3 supplies)。调查时地点帷幕-2。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class Flashlight(CardImplementation):
    card_id = "flashlight_lv0"

    # TODO: Implement investigate action spending 1 supply for -2 shroud
