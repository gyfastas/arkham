"""Opportunist (Level 0) — Rogue Skill.
机会主义者。若检定成功超过3点以上，将此卡返回手牌而非弃置。
"""
from backend.cards.base import CardImplementation
from backend.models.enums import GameEvent, TimingPriority


class Opportunist(CardImplementation):
    card_id = "opportunist_lv0"

    # No event handler needed — return-to-hand logic is handled by the commit system
    # when it checks succeed-by margin after skill test resolution
