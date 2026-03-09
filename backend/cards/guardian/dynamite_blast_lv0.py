"""Dynamite Blast (Level 0) — Guardian Event.
对选定地点的每个敌人造成3点伤害。
"""
from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class DynamiteBlast(CardImplementation):
    card_id = "dynamite_blast_lv0"
    # Skeleton — requires location targeting and AoE damage framework.
