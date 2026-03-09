""""I've had worse..." (Level 4) — Guardian Event.
快速。取消最多5点伤害/恐惧。获得等同于取消数量的资源。
"""
from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class IveHadWorse(CardImplementation):
    card_id = "ive_had_worse_lv4"
    # Skeleton — requires damage/horror cancellation framework and resource gain.
