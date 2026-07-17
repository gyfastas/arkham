"""Abandoned and Alone — Neutral Treachery, Signature Weakness (Wendy Adams).
揭示：受到2点直接恐惧。将你弃牌堆中的所有牌移出游戏。

简化说明：
- 移出游戏的牌记录在 scenario.vars["removed_from_game"]（引擎无独立移除区）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class AbandonedAndAlone(CardImplementation):
    card_id = "abandoned_and_alone"

    @on_event(GameEvent.CARD_DRAWN, priority=TimingPriority.WHEN)
    def revelation(self, ctx):
        if ctx.extra.get("card_id") != "abandoned_and_alone":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if "abandoned_and_alone" in inv.hand:
            inv.hand.remove("abandoned_and_alone")

        # 2点直接恐惧（不分配）
        inv.horror += 2

        # 弃牌堆所有牌移出游戏
        scenario = getattr(ctx.game_state, "scenario", None)
        if scenario is not None:
            removed = scenario.vars.setdefault("removed_from_game", [])
            removed.extend(inv.discard)
        inv.discard.clear()

        # 本卡进入弃牌堆
        inv.discard.append("abandoned_and_alone")
        ctx.extra["abandoned_and_alone_resolved"] = True
