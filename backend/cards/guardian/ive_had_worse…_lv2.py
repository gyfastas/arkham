""""I've had worse…" (Level 2) — Guardian Event. (05315)
快速。在你被造成伤害和/或恐惧时打出。取消刚被造成的至多2点伤害和/或恐惧。
然后，获得等量资源。

实现说明（同 ive_had_worse_lv4，取消上限为2）：
- 从手牌中自动触发（"快速"时机由玩家选择简化为自动）：你被造成伤害/恐惧时，
  若手牌中有本卡则自动打出并结算。
- 取消经由 DAMAGE_ASSIGNED / HORROR_ASSIGNED 的 ctx.modify_amount 表达，
  引擎据此减少调查员承受的部分（盟友分担不受影响）。
- 简化：一次攻击同时造成伤害与恐惧时，两个事件各自结算（各取消至多2点），
  与官方"合计至多2点"略有差异。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority

_CANCEL_CAP = 2


class IveHadWorseLv2(CardImplementation):
    card_id = "ive_had_worse…_lv2"

    def _maybe_play(self, ctx) -> None:
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if self.card_id not in inv.hand:
            return
        if (ctx.amount or 0) < 1:
            return
        cd = ctx.game_state.get_card_data(self.card_id)
        cost = getattr(cd, "cost", 0) or 0 if cd else 0
        if inv.resources < cost:
            return
        inv.resources -= cost
        inv.hand.remove(self.card_id)
        inv.discard.append(self.card_id)
        cancelled = min(ctx.amount, _CANCEL_CAP)
        ctx.modify_amount(-cancelled, "ive_had_worse_cancel")
        inv.resources += cancelled
        ctx.extra["ive_had_worse_cancelled"] = cancelled
        ctx.game_state.log_effect(
            f"🛡️ 我见过更糟的……：取消{cancelled}点并获得{cancelled}资源")

    @on_event(GameEvent.DAMAGE_ASSIGNED, priority=TimingPriority.WHEN)
    def cancel_damage(self, ctx):
        self._maybe_play(ctx)

    @on_event(GameEvent.HORROR_ASSIGNED, priority=TimingPriority.WHEN)
    def cancel_horror(self, ctx):
        self._maybe_play(ctx)
