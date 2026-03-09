"""Survival Instinct (Level 0) — Survivor Skill.
求生本能。闪避检定成功时，可脱离所有敌人并移动到相邻地点。
"""

from backend.cards.base import CardImplementation


class SurvivalInstinct(CardImplementation):
    card_id = "survival_instinct_lv0"
    # No handler — provides 1 agility icon and has a conditional
    # movement effect that requires full evasion engine support.
