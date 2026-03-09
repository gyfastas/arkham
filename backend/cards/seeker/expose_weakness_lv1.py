"""Expose Weakness (Level 1) — Seeker Event, Fast.
快速事件：进行智力检定（难度为敌人战斗值）。成功则降低该敌人战斗值，降低量等于超出值。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class ExposeWeakness(CardImplementation):
    card_id = "expose_weakness_lv1"

    @on_event(
        GameEvent.CARD_PLAYED,
        priority=TimingPriority.WHEN,
    )
    def test_intellect_vs_enemy(self, ctx):
        """Test intellect vs enemy's fight value. On success, reduce
        enemy's fight value by amount succeeded by.

        Skeleton — requires complex enemy targeting, intellect test
        initiation, and temporary fight value modification tracking.
        """
        pass
