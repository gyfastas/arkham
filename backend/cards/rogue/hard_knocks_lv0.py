"""Hard Knocks (Level 0) — Rogue Asset.
沉重打击。花费1资源：+1战斗值。花费1资源：+1敏捷值。
"""
from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class HardKnocks(CardImplementation):
    card_id = "hard_knocks_lv0"

    # Skeleton: Spend 1 resource for +1 combat or +1 agility during skill tests
    # Requires player choice UI for resource spending during SKILL_VALUE_DETERMINED
