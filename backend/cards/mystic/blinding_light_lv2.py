"""Blinding Light (Level 2) — Mystic Event.
用意志力进行回避。成功则造成2点伤害。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class BlindingLightLv2(CardImplementation):
    card_id = "blinding_light_lv2"

    @on_event(
        GameEvent.CARD_PLAYED,
        priority=TimingPriority.WHEN,
    )
    def evade_with_willpower(self, ctx):
        """Evade using willpower instead of agility. If succeed, deal 2 damage.

        Skeleton — requires evade action override and damage on success.
        """
        pass
