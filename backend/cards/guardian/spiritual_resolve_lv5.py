"""Spiritual Resolve (Level 5) — Guardian Asset, Arcane slot. (06323)
生命3/理智3。多重。
[fast]从你的手牌丢弃一张摒绝杂念：治愈本摒绝杂念的所有伤害和恐惧。

简化说明：
- 启动能力为公开方法 activate_heal()（[fast]，由会话层调用）：手牌中有另一张
  摒绝杂念时将其弃置，治愈在场本卡的全部伤害与恐惧。
- 多重的牌组构建规则不在效果实现范围。
"""

from backend.cards.base import CardImplementation


class SpiritualResolve(CardImplementation):
    card_id = "spiritual_resolve_lv5"
    activations = [{
        "id": "heal",
        "label": "弃手牌中一张摒绝杂念：治愈本卡全部伤害/恐惧",
        "method": "activate_heal",
        "actions": 0,
    }]

    def activate_heal(self, game_state, investigator_id: str) -> bool:
        """[fast] 弃手牌中一张同名卡：治愈在场本卡的所有伤害和恐惧。"""
        inv = game_state.get_investigator(investigator_id)
        inst = game_state.get_card_instance(self.instance_id)
        if inv is None or inst is None or self.instance_id not in inv.play_area:
            return False
        if self.card_id not in inv.hand:
            return False
        if inst.damage <= 0 and inst.horror <= 0:
            return False

        inv.hand.remove(self.card_id)
        inv.discard.append(self.card_id)
        healed_damage, healed_horror = inst.damage, inst.horror
        inst.damage = 0
        inst.horror = 0
        game_state.log_effect(
            f"🧘 摒绝杂念：弃置手牌中一张摒绝杂念，治愈{healed_damage}点伤害"
            f"与{healed_horror}点恐惧")
        return True
