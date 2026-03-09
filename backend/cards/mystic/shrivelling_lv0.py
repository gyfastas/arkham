"""Shrivelling (Level 0) — Mystic Asset, Arcane slot.
使用（4充能）。用意志力代替战斗进行攻击，+1伤害。揭示特殊标记时承受1点恐惧。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class Shrivelling(CardImplementation):
    card_id = "shrivelling_lv0"

    @on_event(
        GameEvent.CARD_PLAYED,
        priority=TimingPriority.WHEN,
    )
    def fight_with_willpower(self, ctx):
        """Fight using willpower instead of combat. +1 damage.

        Skeleton — requires fight action override, charge tracking,
        and chaos token reveal callback for horror.
        """
        pass
