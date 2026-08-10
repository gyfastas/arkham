"""Spirit of Humanity (Level 2) — Survivor Asset, Arcane slot. (07229)
[fast] 消耗人性抉择并受到1点伤害和1点恐惧：加入2个 [bless] 标记到混乱袋。
[fast] 消耗人性抉择并加入2个 [curse] 标记到混乱袋：治愈1点伤害和1点恐惧。

简化说明：
- 两个快速能力经 activations 公开方法实现（会话层 ACTIVATE_CARD 路由）。
- "受到1点伤害和1点恐惧"直接加在调查员上（不经伤害分配窗口，从简）。
- 混沌袋经 bind_chaos_bag 注入（registry 入场激活时接线；未绑定则失败）。
"""

from backend.cards.base import CardImplementation
from backend.models.enums import ChaosTokenType


class SpiritOfHumanity(CardImplementation):
    card_id = "spirit_of_humanity_lv2"
    activations = [
        {
            "id": "add_bless",
            "label": "消耗+受1伤害1恐惧：加2个祝福标记",
            "method": "activate_bless",
        },
        {
            "id": "add_curse",
            "label": "消耗+加2个诅咒标记：治愈1伤害1恐惧",
            "method": "activate_curse",
        },
    ]

    def bind_chaos_bag(self, chaos_bag) -> None:
        """注入混沌袋（registry.activate_card / 测试接线）。"""
        self._chaos_bag = chaos_bag

    def _ready_instance(self, game_state, investigator_id):
        inv = game_state.get_investigator(investigator_id)
        inst = game_state.get_card_instance(self.instance_id)
        if inv is None or inst is None or inst.exhausted:
            return None, None
        if self.instance_id not in inv.play_area:
            return None, None
        return inv, inst

    def activate_bless(self, game_state, investigator_id: str) -> bool:
        """[fast] 消耗 + 受1伤害1恐惧：加2个祝福标记。"""
        bag = getattr(self, "_chaos_bag", None)
        inv, inst = self._ready_instance(game_state, investigator_id)
        if bag is None or inv is None:
            return False
        inst.exhausted = True
        inv.damage += 1
        inv.horror += 1
        bag.add_token(ChaosTokenType.BLESS)
        bag.add_token(ChaosTokenType.BLESS)
        game_state.log_effect("🕊 人性抉择：受1伤害1恐惧，加入2个祝福标记")
        return True

    def activate_curse(self, game_state, investigator_id: str) -> bool:
        """[fast] 消耗 + 加2个诅咒标记：治愈1伤害1恐惧。"""
        bag = getattr(self, "_chaos_bag", None)
        inv, inst = self._ready_instance(game_state, investigator_id)
        if bag is None or inv is None:
            return False
        inst.exhausted = True
        bag.add_token(ChaosTokenType.CURSE)
        bag.add_token(ChaosTokenType.CURSE)
        inv.damage = max(0, inv.damage - 1)
        inv.horror = max(0, inv.horror - 1)
        game_state.log_effect("🕊 人性抉择：加入2个诅咒标记，治愈1伤害1恐惧")
        return True
