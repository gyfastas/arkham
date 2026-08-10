"""Momentum (Level 1) — Rogue Skill. (06115)
若本次技能检定成功，本阶段内你执行的下一次技能检定难度降低X，X为本次
检定超出难度的数量（至多为3）。

简化说明：
- 投入的技能卡实现仅在检定流程内临时激活（ST.8 注销），跨检定的减难度
  需要留存监听：本卡经 persistent_in_hand 在抽到后持续注册（引擎在手牌
  监听通道），减难度额度存于调查员 active_effects，下一次检定的
  SKILL_TEST_BEGINS 时消耗（引擎允许改写难度，同 flashlight 通道）；
  阶段结束（INVESTIGATION_PHASE_ENDS）未消耗则过期。
- 手牌实例与投入临时实例会同时结算成功事件，二者写同一标记（幂等）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority

_MAX_REDUCTION = 3
_FLAG = "momentum_lv1_reduction"


class Momentum(CardImplementation):
    card_id = "momentum_lv1"
    persistent_in_hand = True  # 跨检定监听减难度窗口（效果在投入后留存）

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.AFTER)
    def arm(self, ctx):
        """成功：记录超出量（至多3），降低本阶段下一次检定的难度。"""
        if "momentum_lv1" not in ctx.committed_cards:
            return
        margin = (ctx.modified_skill or 0) - (ctx.difficulty or 0)
        if margin <= 0:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if not hasattr(inv, "active_effects"):
            inv.active_effects = {}
        inv.active_effects[_FLAG] = min(_MAX_REDUCTION, margin)

    @on_event(GameEvent.SKILL_TEST_BEGINS, priority=TimingPriority.WHEN)
    def reduce_next_difficulty(self, ctx):
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        effects = getattr(inv, "active_effects", None) or {}
        x = effects.pop(_FLAG, 0)
        if x <= 0 or ctx.difficulty is None:
            return
        ctx.difficulty = max(0, ctx.difficulty - x)
        ctx.extra["momentum_reduction"] = x
        ctx.game_state.log_effect(f"🏃 势如破竹：本次检定难度-{x}")

    @on_event(GameEvent.INVESTIGATION_PHASE_ENDS, priority=TimingPriority.AFTER)
    def expire(self, ctx):
        for inv in ctx.game_state.investigators.values():
            effects = getattr(inv, "active_effects", None)
            if effects:
                effects.pop(_FLAG, None)
