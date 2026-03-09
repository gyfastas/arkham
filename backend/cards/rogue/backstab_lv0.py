"""Backstab (Level 0) — Rogue Event.
背刺。战斗：使用敏捷代替战斗值，额外+2伤害。
"""
from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class Backstab(CardImplementation):
    card_id = "backstab_lv0"

    # Skeleton: Fight using agility instead of combat, +2 damage
    # Requires fight sub-action with skill substitution
