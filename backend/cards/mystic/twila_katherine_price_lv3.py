"""Twila Katherine Price (Level 3) — Mystic Asset, Ally slot, unique. (06244)
[reaction] 在你花费一张[[法术]]支援卡的1个或更多充能后，消耗本卡：
在该支援卡上放置1充能。

简化/缺口说明：
- 引擎无"花费充能"事件（各法术卡的 activate() 直接扣减 uses），反应
  无法被动触发（引擎缺口）。实现公开 trigger() 反应方法，供会话层在
  法术支援扣减充能后调用；activations 的 target 通道仅支持敌人，故未
  声明 declarative activation。
"""

from backend.cards.base import CardImplementation
from backend.cards.seeker._uses import uses_count, uses_key
from backend.models.enums import CardType


class TwilaKatherinePrice(CardImplementation):
    card_id = "twila_katherine_price_lv3"

    def trigger(self, game_state, investigator_id: str,
                asset_instance_id: str) -> bool:
        """反应：消耗本卡，在刚花费过充能的法术支援上放置1充能。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None or inst.exhausted:
            return False
        target = game_state.get_card_instance(asset_instance_id)
        if target is None or asset_instance_id not in inv.play_area:
            return False
        cd = game_state.get_card_data(target.card_id)
        if cd is None or cd.type != CardType.ASSET \
                or "spell" not in (cd.traits or []):
            return False
        if uses_key(target, "charges") not in target.uses:
            return False  # 该支援不使用充能
        inst.exhausted = True
        key = uses_key(target, "charges")
        target.uses[key] = uses_count(target, "charges") + 1
        game_state.log_effect(
            f"🎨 特薇拉·凯瑟琳·普莱斯：消耗，"
            f"【{game_state.card_name(target.card_id)}】+1充能")
        return True
