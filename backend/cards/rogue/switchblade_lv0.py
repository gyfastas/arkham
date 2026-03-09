"""Switchblade (Level 0) — Rogue Asset.
弹簧刀。快速打出。战斗：若成功超过2点以上，额外造成1伤害。
"""
from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class Switchblade(CardImplementation):
    card_id = "switchblade_lv0"

    # Skeleton: Fast keyword, Fight action with conditional +1 damage
    # Full implementation requires fight sub-action with succeed-by tracking
