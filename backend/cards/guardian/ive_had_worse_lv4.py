""""I've had worse..." (Level 4) — Guardian Event.
快速。在你被造成伤害和/或恐惧时打出。取消刚被造成的至多5点伤害和/或恐惧。
然后，获得等量资源。

实现说明：
- 从手牌中自动触发（"快速"时机由玩家选择简化为自动）：你被造成伤害/恐惧时，
  若手牌中有本卡则自动打出并结算。
- 取消经由 DAMAGE_ASSIGNED / HORROR_ASSIGNED 的 ctx.modify_amount 表达。
  ⚠️ 引擎当前在发出这两个事件后仍按原分担量结算（engine/damage.py 的
  deal_damage 不使用事件后的 ctx.amount），需要引擎支持取消窗口后
  减伤才真正生效；资源补偿在本卡内即时结算。
- 简化：一次攻击同时造成伤害与恐惧时，两个事件各自结算（各取消至多5点），
  与官方"合计至多5点"略有差异。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority

_CANCEL_CAP = 5


class IveHadWorse(CardImplementation):
    card_id = "ive_had_worse_lv4"

    def _maybe_play(self, ctx) -> None:
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if "ive_had_worse_lv4" not in inv.hand:
            return
        if (ctx.amount or 0) < 1:
            return
        cd = ctx.game_state.get_card_data("ive_had_worse_lv4")
        cost = getattr(cd, "cost", 0) or 0 if cd else 0
        if inv.resources < cost:
            return
        inv.resources -= cost
        inv.hand.remove("ive_had_worse_lv4")
        inv.discard.append("ive_had_worse_lv4")
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
