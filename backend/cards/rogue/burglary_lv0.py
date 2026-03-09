"""Burglary (Level 0) — Rogue Asset.
夜盗。消耗：调查，若成功则获得3资源而非线索。
"""
from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class Burglary(CardImplementation):
    card_id = "burglary_lv0"

    # Skeleton: Exhaust to investigate; on success gain 3 resources instead of clues
    # Requires investigation sub-action with result replacement
