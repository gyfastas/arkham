"""Disc of Itzamna (Level 2) — Seeker Asset, Accessory slot.
反应 - 当一个非精英敌人将在你的地点生成时：弃置伊察姆纳圆盘，改为将该敌人弃置（不生成）。

说明：
- 生成拦截在 official_core._spawn_enemy_from_encounter 中实现
  （检查你场上是否有 disc_of_itzamna_lv2）。本类提供 is_disc() 判定辅助。
"""

from backend.cards.base import CardImplementation


class DiscOfItzamna(CardImplementation):
    card_id = "disc_of_itzamna_lv2"

    @staticmethod
    def is_disc(card_id: str) -> bool:
        return card_id == "disc_of_itzamna_lv2"
