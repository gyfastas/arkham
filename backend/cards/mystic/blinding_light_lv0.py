"""Blinding Light (Level 0) — Mystic Event.
用意志力进行回避。成功则造成1点伤害。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class BlindingLight(CardImplementation):
    card_id = "blinding_light_lv0"

    @on_event(
        GameEvent.CARD_PLAYED,
        priority=TimingPriority.WHEN,
    )
    def evade_with_willpower(self, ctx):
        """Evade using willpower instead of agility. If succeed, deal 1 damage.

        Skeleton — requires evade action override and damage on success.
        """
        pass
