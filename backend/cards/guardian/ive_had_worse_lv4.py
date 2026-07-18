"""I've Had Worse (Level 4) — Guardian Event.
快速。在你将受到3点或更多伤害或恐惧时打出。取消最多3点该伤害或恐惧。

简化说明：
- 从手牌中自动触发（"快速"时机由玩家选择简化为自动）：
  将受到≥3点伤害/恐惧时，自动从手牌打出并取消3点。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class IveHadWorse(CardImplementation):
    card_id = "ive_had_worse_lv4"

    def _maybe_play(self, ctx) -> None:
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if "ive_had_worse_lv4" not in inv.hand:
            return
        if (ctx.amount or 0) < 3:
            return
        cd = ctx.game_state.get_card_data("ive_had_worse_lv4")
        cost = getattr(cd, "cost", 0) or 0 if cd else 0
        if inv.resources < cost:
            return
        inv.resources -= cost
        inv.hand.remove("ive_had_worse_lv4")
        inv.discard.append("ive_had_worse_lv4")
        ctx.modify_amount(-3, "ive_had_worse_cancel")
        ctx.extra["ive_had_worse_played"] = True

    @on_event(GameEvent.DAMAGE_DEALT, priority=TimingPriority.WHEN)
    def cancel_damage(self, ctx):
        self._maybe_play(ctx)

    @on_event(GameEvent.HORROR_DEALT, priority=TimingPriority.WHEN)
    def cancel_horror(self, ctx):
        self._maybe_play(ctx)
