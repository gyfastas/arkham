"""Perseverance (Level 0) — Survivor Event. (03229 批次)
Fast. Play when you are assigned damage and/or horror that would defeat you.
Cancel up to 4 of that damage and/or horror.

简化说明：
- 从手牌中自动触发（同 devils_luck 模式）：你被分配伤害/恐惧且本次承受
  后将达上限被击败时，若手牌中有本卡且资源足够，自动打出并取消至多4点
  （经 DAMAGE_ASSIGNED / HORROR_ASSIGNED 的 ctx.modify_amount 表达）。
- 一次攻击同时造成伤害与恐惧时，两个事件各自结算（各取消至多4点），
  与官方"合计至多4点"略有差异（同 devils_luck 的既有简化）。
- 盟友分摊部分在事件前已完成，取消仅作用于调查员承受部分（引擎机制）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority

_CANCEL_CAP = 4


class Perseverance(CardImplementation):
    card_id = "perseverance_lv0"
    persistent_in_hand = True  # 在手牌中持续监听致命伤害窗口

    def _maybe_play(self, ctx, *, damage: bool) -> None:
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.card_id not in inv.hand:
            return
        amount = ctx.amount or 0
        if amount < 1:
            return
        # 仅当本次分配将导致被击败时才可打出
        if damage:
            would_defeat = inv.damage + amount >= inv.health
        else:
            would_defeat = inv.horror + amount >= inv.sanity
        if not would_defeat:
            return
        cd = ctx.game_state.get_card_data(self.card_id)
        cost = (getattr(cd, "cost", 2) or 2) if cd else 2
        if inv.resources < cost:
            return
        inv.resources -= cost
        inv.hand.remove(self.card_id)
        inv.discard.append(self.card_id)
        cancelled = min(amount, _CANCEL_CAP)
        ctx.modify_amount(-cancelled, "perseverance_cancel")
        ctx.extra["perseverance_cancelled"] = cancelled
        ctx.game_state.log_effect(
            f"🛡️ 坚韧不拔：取消{cancelled}点伤害/恐惧")

    @on_event(GameEvent.DAMAGE_ASSIGNED, priority=TimingPriority.WHEN)
    def cancel_damage(self, ctx):
        self._maybe_play(ctx, damage=True)

    @on_event(GameEvent.HORROR_ASSIGNED, priority=TimingPriority.WHEN)
    def cancel_horror(self, ctx):
        self._maybe_play(ctx, damage=False)
