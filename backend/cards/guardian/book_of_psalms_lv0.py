"""Book of Psalms (Level 0) — Guardian Asset, Hand slot. (07017)
使用(4秘密)。
[行动]花费1秘密：治愈你所在地点一名调查员的1点恐惧。将2个[bless]标记
加入混乱袋。

简化说明：
- 治愈目标自动选择：优先自己；自己无恐惧时选同地点第一位有恐惧的调查员
  （官方为玩家选择目标；会话层 ACTIVATE_CARD 通道不传调查员目标）。
- 祝福标记经 bind_chaos_bag() 注入的混沌袋加入（registry 已接线）。
- 数据 uses 键兼容 "secrets"/"secretss"（抓取复数化瑕疵）。
"""

from backend.cards.base import CardImplementation
from backend.models.enums import ChaosTokenType


class BookOfPsalms(CardImplementation):
    card_id = "book_of_psalms_lv0"
    activations = [{
        "id": "heal",
        "label": "花1秘密：治愈同地点1恐惧，袋中加入2祝福",
        "method": "activate",
        "actions": 1,
    }]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._chaos_bag = None

    def bind_chaos_bag(self, chaos_bag) -> None:
        """注入游戏混沌袋（registry.activate_card 自动调用）。"""
        self._chaos_bag = chaos_bag

    def activate(self, game_state, investigator_id: str) -> bool:
        """花费1秘密：治愈同地点一名调查员1点恐惧，袋中加2个祝福标记。"""
        inv = game_state.get_investigator(investigator_id)
        inst = game_state.get_card_instance(self.instance_id)
        if inv is None or inst is None or self.instance_id not in inv.play_area:
            return False
        key = "secrets" if "secrets" in inst.uses else "secretss"
        if inst.uses.get(key, 0) <= 0:
            return False

        # 目标自动选择：优先自己，其次同地点有恐惧的调查员
        target = inv if inv.horror > 0 else None
        if target is None:
            for other in game_state.get_investigators_at_location(inv.location_id):
                if other.horror > 0:
                    target = other
                    break
        if target is None:
            return False

        inst.uses[key] -= 1
        target.horror -= 1
        if self._chaos_bag is not None:
            self._chaos_bag.add_token(ChaosTokenType.BLESS)
            self._chaos_bag.add_token(ChaosTokenType.BLESS)
        game_state.log_effect("📖 《圣经‧诗篇》：治愈1点恐惧，混沌袋加入2个祝福标记")
        return True
