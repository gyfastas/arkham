"""Devil's Luck (Level 1) — Survivor Event.
快速。在你受到伤害和/或恐惧时打出。
取消最多10点你刚才受到的伤害和/或恐惧。放逐吉人天相。

简化说明：
- 从手牌中自动触发（同 ive_had_worse 模式）：你被分配伤害/恐惧时，若
  手牌中有吉人天相且资源足够，自动打出并取消（经 DAMAGE_ASSIGNED /
  HORROR_ASSIGNED 的 ctx.modify_amount 表达；引擎已支持事件后按减少量
  结算调查员承受部分）。
- 一次攻击同时造成伤害与恐惧时，两个事件各自结算（各取消至多10点），
  与官方"合计至多10点"略有差异（同 ive_had_worse 的既有简化）。
- 盟友分摊部分在事件前已完成，取消仅作用于调查员承受部分（引擎机制）。
- 放逐：引擎无放逐区，登记在 scenario.vars["exiled_cards"]，不进入
  弃牌堆（引擎缺口，见报告）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority

_CANCEL_CAP = 10


class DevilsLuck(CardImplementation):
    card_id = "devils_luck_lv1"
    persistent_in_hand = True  # 在手牌中持续监听受伤窗口

    def _maybe_play(self, ctx) -> None:
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if self.card_id not in inv.hand:
            return
        if (ctx.amount or 0) < 1:
            return
        cd = ctx.game_state.get_card_data(self.card_id)
        cost = (getattr(cd, "cost", 1) or 1) if cd else 1
        if inv.resources < cost:
            return
        inv.resources -= cost
        inv.hand.remove(self.card_id)
        # 放逐（不进入弃牌堆）
        ctx.game_state.scenario.vars.setdefault(
            "exiled_cards", []).append(self.card_id)
        cancelled = min(ctx.amount, _CANCEL_CAP)
        ctx.modify_amount(-cancelled, "devils_luck_cancel")
        ctx.extra["devils_luck_cancelled"] = cancelled
        ctx.game_state.log_effect(
            f"😈 吉人天相：取消{cancelled}点伤害/恐惧，放逐")

    @on_event(GameEvent.DAMAGE_ASSIGNED, priority=TimingPriority.WHEN)
    def cancel_damage(self, ctx):
        self._maybe_play(ctx)

    @on_event(GameEvent.HORROR_ASSIGNED, priority=TimingPriority.WHEN)
    def cancel_horror(self, ctx):
        self._maybe_play(ctx)
