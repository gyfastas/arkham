"""Say Your Prayers (Level 0) — Neutral Skill (Desperate).
4个意志图标由 skill_icons 数据经提交流程自动结算。
仅当你剩余神智值≤3时才可投入技能检定。每次检定最多投入1张。

简化说明：
- "剩余神智≤3才可投入"的限制由 can_commit() 表达，但引擎提交通道
  （skill_test._st2_commit / 会话层投入校验）目前不调用它——需要引擎/会话
  侧接线（与 inquiring_mind_lv0 同一缺口）。
- "每次检定最多投入1张"同样需要提交窗口校验，暂由会话层负责。
"""

from backend.cards.base import CardImplementation


class SayYourPrayers(CardImplementation):
    card_id = "say_your_prayers_lv0"

    def can_commit(self, game_state, investigator_id: str) -> bool:
        """官方投入限制：仅当你剩余神智值≤3时可投入本卡。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return False
        return inv.remaining_sanity <= 3
