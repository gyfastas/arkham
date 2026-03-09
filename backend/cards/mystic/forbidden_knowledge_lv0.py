"""Forbidden Knowledge (Level 0) — Mystic Asset.
使用（4秘密）。消耗并承受1点恐惧：将1个秘密移至资源池作为资源。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class ForbiddenKnowledge(CardImplementation):
    card_id = "forbidden_knowledge_lv0"

    @on_event(
        GameEvent.CARD_PLAYED,
        priority=TimingPriority.WHEN,
    )
    def convert_secret(self, ctx):
        """Exhaust and take 1 horror: Move 1 secret to resource pool as resource.

        Skeleton — requires exhaust/uses tracking and horror assignment.
        """
        pass
