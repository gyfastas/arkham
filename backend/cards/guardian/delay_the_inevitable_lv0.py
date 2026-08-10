"""Delay the Inevitable (Level 0) — Guardian Event. (05021)
快速。仅在你的回合中打出。叠加到你所在地点的一名调查员上，由其控制。
[反应]当你被造成伤害和/或恐惧时：弃置劫数延后，取消刚造成的
所有伤害和/或恐惧。
强制 - 当神话阶段结束时：你必须花费2资源，否则弃置劫数延后。

简化说明：
- 叠加目标简化为持有者自己（官方可为同地点任一调查员；会话层 PLAY 通道
  不传目标）。叠加关系记录在 scenario.vars["delay_the_inevitable"]
  （事件卡结算后入弃牌堆，叠加实体未实现，同 ambush 惯例）。
- 取消简化为自动触发：被叠加者首次被分配伤害/恐惧时取消全部调查员份额
  （引擎在分配事件前已完成盟友分担，盟友份额不在取消范围内——与
  ive_had_worse 同一引擎边界）。
- 神话阶段结束的维持费用简化为自动支付（资源≥2时扣2保留，否则弃置标记；
  官方为玩家选择支付或弃置）。
- ⚠️ 事件实现实例在 ROUND_ENDS 被引擎清理；跨回合后取消与维持费用均不再
  生效（引擎缺口，同 snare_trap/barricade 跨轮监听缺口，见报告）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority

VAR = "delay_the_inevitable"
_UPKEEP_COST = 2


class DelayTheInevitable(CardImplementation):
    card_id = "delay_the_inevitable_lv0"

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def attach(self, ctx):
        """打出时：叠加到持有者自己。"""
        if ctx.extra.get("card_id") != self.card_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        ctx.game_state.scenario.vars[VAR] = {
            "investigator_id": inv.investigator_id,
        }
        ctx.extra["delay_the_inevitable_attached"] = inv.investigator_id
        ctx.game_state.log_effect("⏳ 劫数延后：叠加到你身上")

    def _try_cancel(self, ctx, kind: str) -> None:
        marker = ctx.game_state.scenario.vars.get(VAR)
        if not marker or marker.get("investigator_id") != ctx.investigator_id:
            return
        if (ctx.amount or 0) <= 0:
            return
        ctx.game_state.scenario.vars.pop(VAR, None)
        ctx.cancel()
        ctx.extra["delay_the_inevitable_cancelled"] = kind
        ctx.game_state.log_effect(f"⏳ 劫数延后：弃置，取消刚造成的全部{kind}")

    @on_event(GameEvent.DAMAGE_ASSIGNED, priority=TimingPriority.WHEN)
    def cancel_damage(self, ctx):
        """[反应]被造成伤害时：弃置本卡，取消全部伤害。"""
        self._try_cancel(ctx, "伤害")

    @on_event(GameEvent.HORROR_ASSIGNED, priority=TimingPriority.WHEN)
    def cancel_horror(self, ctx):
        """[反应]被造成恐惧时：弃置本卡，取消全部恐惧。"""
        self._try_cancel(ctx, "恐惧")

    @on_event(GameEvent.MYTHOS_PHASE_ENDS, priority=TimingPriority.FORCED)
    def upkeep_cost(self, ctx):
        """强制 - 神话阶段结束时：花费2资源，否则弃置本卡。"""
        marker = ctx.game_state.scenario.vars.get(VAR)
        if not marker:
            return
        inv = ctx.game_state.get_investigator(marker.get("investigator_id"))
        if inv is None:
            ctx.game_state.scenario.vars.pop(VAR, None)
            return
        if inv.resources >= _UPKEEP_COST:
            inv.resources -= _UPKEEP_COST
            ctx.extra["delay_the_inevitable_upkeep"] = "paid"
            ctx.game_state.log_effect("⏳ 劫数延后：神话阶段结束，花费2资源维持")
        else:
            ctx.game_state.scenario.vars.pop(VAR, None)
            ctx.extra["delay_the_inevitable_upkeep"] = "discarded"
            ctx.game_state.log_effect("⏳ 劫数延后：无法支付2资源，弃置")
