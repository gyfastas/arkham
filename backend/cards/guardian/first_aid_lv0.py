"""First Aid (Level 0) — Guardian Asset.
使用（3补给）。花费1补给：治疗你所在地点一名调查员1点伤害或恐惧。
"""
from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class FirstAid(CardImplementation):
    card_id = "first_aid_lv0"
    # Skeleton — requires activated ability framework for spend-supply actions.
