"""Mind Wipe (Level 1) — Mystic Event.
快速。将一个非精英敌人的文本框清空至阶段结束。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class MindWipe(CardImplementation):
    card_id = "mind_wipe_lv1"

    @on_event(
        GameEvent.CARD_PLAYED,
        priority=TimingPriority.WHEN,
    )
    def blank_enemy(self, ctx):
        """Fast. Blank a non-Elite enemy's text until end of phase.

        Skeleton — requires enemy targeting and text blanking system.
        """
        pass
