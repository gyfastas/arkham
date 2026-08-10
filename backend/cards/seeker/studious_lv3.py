"""Studious (Level 3) — Seeker Asset (Permanent). (05276)
永久。
你每场游戏开始时的起始手牌中拥有额外1张卡牌。

简化说明：
- "永久"为构筑规则（开局即生效、不占牌组），游戏内无事件效果；
- 引擎 Game.setup() 固定抽5张起始手牌，没有永久卡钩子（引擎缺口）；
  提供公开方法 apply_opening_hand()：起手结算后额外抽1张（官方为起手
  多抽1张后正常调度，此处简化为调度后补抽），由会话层在开局调用；
- opening_hand_bonus() 供会话层在 setup 流程查询加值（每张苦心钻研+1）。
"""

from backend.cards.base import CardImplementation


class Studious(CardImplementation):
    card_id = "studious_lv3"

    @staticmethod
    def opening_hand_bonus() -> int:
        """起始手牌额外张数。"""
        return 1

    def apply_opening_hand(self, game_state, investigator_id: str) -> bool:
        """开局起始手牌额外抽1张（牌堆为空则无事发生）。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or not inv.deck:
            return False
        inv.hand.append(inv.deck.pop(0))
        game_state.log_effect("🎓 苦心钻研：起始手牌额外抽1张")
        return True
