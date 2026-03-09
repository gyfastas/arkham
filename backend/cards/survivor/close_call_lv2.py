"""Close Call (Level 2) — Survivor Event.
千钧一发。快速。闪避非精英敌人后，将其洗入遭遇牌堆。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class CloseCall(CardImplementation):
    card_id = "close_call_lv2"

    # TODO: Implement fast play after evading non-Elite enemy
    # shuffle that enemy into the encounter deck
