"""Relic Hunter (Level 3) — Neutral Asset (Permanent).
你获得1个额外的饰品槽位。
"""

from backend.cards.neutral.charisma_lv3 import Charisma
from backend.models.enums import SlotType


class RelicHunter(Charisma):
    card_id = "relic_hunter_lv3"
    slot_type = SlotType.ACCESSORY
    bonus = 1
