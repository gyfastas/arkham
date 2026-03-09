"""Shotgun (Level 4) — Guardian Asset, 2x Hand slots.
使用（2弹药）。战斗。+3战斗力。伤害=超出点数（最少1，最多5）。
"""
from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class Shotgun(CardImplementation):
    card_id = "shotgun_lv4"
    # Skeleton — requires variable damage calculation based on success margin.
    # +3 combat bonus during fight, damage = max(1, min(5, amount_succeeded_by)).
