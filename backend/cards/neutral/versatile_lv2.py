"""Versatile (Level 2) — Neutral Asset (Permanent, Talent).
永久。
你的牌组卡牌张数+5。
你的调查员的牌组构建选项获得："1张任何职阶（守卫/探求者/游荡者/
神秘学者/生存者）的其它0级卡牌"。

简化说明：
- 纯牌组构筑效果，无局内行为。"永久"（开局即在场）与牌组张数/构筑选项
  由会话/构筑层在牌组校验时读取 deck_size_bonus() 与
  added_deckbuilding_options()（与 stick_to_the_plan_lv3 的"永久由构筑
  层处理"同一惯例）。
"""

from backend.cards.base import CardImplementation


class Versatile(CardImplementation):
    card_id = "versatile_lv2"

    def deck_size_bonus(self, game_state=None, investigator_id=None) -> int:
        """牌组卡牌张数 +5。"""
        return 5

    def added_deckbuilding_options(self, game_state=None,
                                   investigator_id=None) -> dict:
        """追加的构筑选项：任意职阶的1张其它0级卡。"""
        return {
            "count": 1,
            "level": 0,
            "classes": ["guardian", "seeker", "rogue", "mystic", "survivor"],
        }
