"""Dodge (Level 0) — Guardian Event.
快速。当一个敌人攻击时打出。取消该攻击。
"""
from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class Dodge(CardImplementation):
    card_id = "dodge_lv0"
    # Skeleton — requires enemy attack cancellation framework.
    # Would listen to ENEMY_ATTACK event and set ctx.cancel = True.
