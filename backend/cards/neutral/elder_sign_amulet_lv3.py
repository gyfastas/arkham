"""Elder Sign Amulet (Level 3) — Neutral Asset, Accessory slot.
官方卡面无文字能力：远古印记护身符自带4理智，用于承恐（soak）。

简化说明：
- 承恐经引擎 DamageEngine 的 horror_assignment 通道分配到带理智值的
  支援；但 get_ally_soak_targets() 目前只把盟友列为承恐目标，非盟友
  支援（如本卡）的承恐分配在生产链路中不可达，需引擎/会话层扩展，
  本卡实现暂无任何主动效果（数据中的 sanity: 4 即为全部规则内容）。
"""

from backend.cards.base import CardImplementation


class ElderSignAmulet(CardImplementation):
    card_id = "elder_sign_amulet_lv3"
