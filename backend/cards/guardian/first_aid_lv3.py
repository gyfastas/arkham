"""First Aid (Level 3) — Guardian Asset.
使用（4补给）。花费1补给：治疗1点伤害和1点恐惧。
"""
from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class FirstAidLv3(CardImplementation):
    card_id = "first_aid_lv3"
    # Skeleton — requires activated ability framework for spend-supply actions.
    # Upgraded version heals both 1 damage AND 1 horror (not "or").
