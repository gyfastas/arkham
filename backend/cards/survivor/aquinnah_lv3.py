"""Aquinnah (Level 3) — Survivor Asset, Ally slot.
[reaction] When an enemy attacks you, exhaust Aquinnah and deal 1 horror to her:
Deal that enemy's damage to any enemy at your location, instead.
(You still take horror dealt by the attack.)

与 lv1 的差异：目标可以是任意敌人（含攻击者本身），默认选攻击者。
"""

from backend.cards.survivor.aquinnah_lv1 import AquinnahLv1


class AquinnahLv3(AquinnahLv1):
    card_id = "aquinnah_lv3"
    target_any_enemy = True
