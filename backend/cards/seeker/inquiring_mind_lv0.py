"""Inquiring Mind (Level 0) — Seeker Skill.
仅当你所在地点有线索时，才能投入技能检定。（3个狂野图标由数据提供。）

简化说明：
- 3 个狂野图标由 skill_icons 数据经技能卡提交流程自动结算，无需 handler；
- "所在地点有线索才能投入"的限制由 can_commit() 表达，但引擎提交通道
  （skill_test._st2_commit / 会话层投入校验）目前不调用它——需要引擎/会话
  侧接线，已列入审计报告待主代理处理。
"""

from backend.cards.base import CardImplementation


class InquiringMind(CardImplementation):
    card_id = "inquiring_mind_lv0"

    def can_commit(self, game_state, investigator_id: str) -> bool:
        """官方投入限制：仅当你所在地点有线索时可投入本卡。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return False
        location = game_state.get_location(inv.location_id)
        return bool(location and location.clues > 0)
