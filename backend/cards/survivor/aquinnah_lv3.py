"""Aquinnah (Level 3) — Survivor Asset, Ally slot.
反应 - 当你受到敌人伤害时：弃置安奎娜。取消该伤害，改为对该敌人造成2点伤害。
"""

from backend.cards.survivor.aquinnah_lv1 import AquinnahLv1


class AquinnahLv3(AquinnahLv1):
    card_id = "aquinnah_lv3"
    reflect_damage = 2
