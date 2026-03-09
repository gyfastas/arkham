"""Lockpicks (Level 1) — Rogue Asset.
撬锁工具。使用（3补给）。消耗并花费1补给：调查，可用敏捷代替理智。
"""
from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class Lockpicks(CardImplementation):
    card_id = "lockpicks_lv1"

    # Skeleton: Uses (3 supplies). Exhaust + spend 1 supply: Investigate using agility.
    # Requires investigation sub-action with skill substitution and supply tracking
