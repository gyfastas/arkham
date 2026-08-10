"""Analytical Mind (Level 0) — Neutral Asset, Signature (Minh Thi Phan).
你可以投入1张卡牌到其他地点调查员进行的每次技能检定。
[reaction]你在技能检定中投入正好1张卡牌后，消耗缜密分析：抽取1张卡牌。

简化说明：
- "投入1张卡到其他地点调查员的检定"是投入窗口权限，引擎提交通道不支持
  跨调查员/跨地点投入，由 can_commit_to_other_location() 表达，待会话层接线。
- [reaction] 覆盖"潘明自己检定时投入正好1张卡"的分支；为他人检定投入
  1张卡的分支依赖上述投入窗口，接线前不触发。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class AnalyticalMind(CardImplementation):
    card_id = "analytical_mind_lv0"

    @on_event(GameEvent.SKILL_TEST_COMMIT, priority=TimingPriority.REACTION)
    def draw_on_single_commit(self, ctx):
        """投入正好1张卡后，消耗本卡：抽1张。"""
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is None or inst.exhausted:
            return
        if ctx.investigator_id != inst.owner_id:
            return
        if len(ctx.committed_cards or []) != 1:
            return
        inst.exhausted = True
        inv = ctx.game_state.get_investigator(inst.owner_id)
        if inv is not None and inv.deck:
            card_id = inv.deck.pop(0)
            inv.hand.append(card_id)
            ctx.game_state.log_effect(
                f"🧠 缜密分析：投入正好1张卡，抽到【{ctx.game_state.card_name(card_id)}】"
            )

    def can_commit_to_other_location(self, game_state, investigator_id) -> bool:
        """官方：你可投入1张卡到其他地点调查员的检定（引擎投入窗口未接线）。"""
        inst = game_state.get_card_instance(self.instance_id)
        return inst is not None and inst.owner_id == investigator_id
