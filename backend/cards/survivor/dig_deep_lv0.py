"""Dig Deep (Level 0) — Survivor Asset.
深挖。花费1资源：+1意志力。花费1资源：+1敏捷。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class DigDeep(CardImplementation):
    card_id = "dig_deep_lv0"

    # TODO: Implement spend 1 resource for +1 willpower or +1 agility
