"""Blasphemous Covenant (Level 2) — Seeker Asset (Permanent). (07113)
永久。每牌组限1张[[契约]]。
[反应]当你所在地点的一名调查员在技能检定中揭示[诅咒]标记时，横置亵渎契约：
将该标记的修正值视为+1，而非其原本修正值。本次检定结束后，将该标记放回
混沌袋。

简化说明：
- 永久/契约限1为构筑规则，由构筑层处理；
- 反应自动触发（官方为玩家选择是否横置；+1替代-2为纯收益）：自动横置并
  将修正值设为+1；
- "检定结束后放回混沌袋"：本引擎混沌袋抽取为非破坏性（标记从不离袋，
  见 chaos.ChaosBag.draw），故该条款天然满足，无需处理——官方规则中
  祝福/诅咒标记揭示后应移出袋外，引擎偏差另见报告。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import ChaosTokenType, GameEvent, TimingPriority


class BlasphemousCovenant(CardImplementation):
    card_id = "blasphemous_covenant_lv2"

    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.WHEN)
    def curse_becomes_plus_one(self, ctx):
        """你所在地点的调查员揭示[诅咒]时：横置本卡，修正值视为+1。"""
        if ctx.chaos_token != ChaosTokenType.CURSE:
            return
        holder = None
        for inv in ctx.game_state.investigators.values():
            if self.instance_id in inv.play_area:
                holder = inv
                break
        if holder is None:
            return
        tester = ctx.game_state.get_investigator(ctx.investigator_id)
        if tester is None or tester.location_id != holder.location_id:
            return
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is None or inst.exhausted:
            return

        inst.exhausted = True
        ctx.modify_amount(1 - ctx.amount, "blasphemous_covenant")
        ctx.extra["blasphemous_covenant_applied"] = True
        ctx.game_state.log_effect(
            "😈 亵渎契约：横置，[诅咒]标记修正值视为+1"
        )
