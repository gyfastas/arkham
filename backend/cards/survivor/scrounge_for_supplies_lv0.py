"""Scrounge for Supplies (Level 0) — Survivor Event. (06165)
Choose a level 0 card in your discard pile. Add the chosen card to your hand.

简化说明：
- 目标选择自动化：取弃牌堆中第一张等级0的卡（官方为玩家选择）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class ScroungeForSupplies(CardImplementation):
    card_id = "scrounge_for_supplies_lv0"

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def recover_level_zero(self, ctx):
        if ctx.extra.get("card_id") != self.card_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        for cid in list(inv.discard):
            cd = ctx.game_state.get_card_data(cid)
            if cd is not None and (cd.level or 0) == 0:
                inv.discard.remove(cid)
                inv.hand.append(cid)
                ctx.extra["scrounge_recovered"] = cid
                ctx.game_state.log_effect(
                    f"🧺 搜寻补给：从弃牌堆取回【{ctx.game_state.card_name(cid)}】")
                return
