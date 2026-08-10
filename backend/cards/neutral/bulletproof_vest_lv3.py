"""Bulletproof Vest (Level 3) — Neutral Asset, Body slot.
官方卡面无文字能力：防弹衣自带4生命值，用于承伤（soak）。

简化说明：
- 承伤经引擎 DamageEngine 的 damage_assignment 通道分配到带生命值的
  支援；但 get_ally_soak_targets() 目前只把盟友列为承伤目标，非盟友
  支援（如本卡）的承伤分配在生产链路中不可达，需引擎/会话层扩展，
  本卡实现暂无任何主动效果（数据中的 health: 4 即为全部规则内容）。
"""

from backend.cards.base import CardImplementation


class BulletproofVest(CardImplementation):
    card_id = "bulletproof_vest_lv3"
