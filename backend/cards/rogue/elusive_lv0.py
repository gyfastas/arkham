"""Elusive (Level 0) — Rogue Event.
逃避隐藏。快速。脱离所有敌人并移动到一个已揭示的无敌人地点。
"""
from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class Elusive(CardImplementation):
    card_id = "elusive_lv0"

    # Skeleton: Fast event. Disengage from all enemies, move to revealed location with no enemies.
    # Requires location selection UI and enemy disengage logic
