"""Crack the Case (Level 0) — Seeker Event.
快速。在一位调查员发现你所在地点的最后一个线索后打出。
位于该地点的调查员获得总计X资源，由你自行分配，X为该地点的隐藏值。

简化说明：
- "由你自行分配"在单人/自动结算中简化为全部给予打出者；
  多人分配由会话层 UI 驱动。打出时机由会话层校验。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class CrackTheCase(CardImplementation):
    card_id = "crack_the_case_lv0"

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def gain_resources(self, ctx):
        """获得等同于所在地点隐藏值的资源。"""
        if ctx.extra.get("card_id") != "crack_the_case_lv0":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        location = ctx.game_state.get_location(inv.location_id)
        if location is None:
            return
        shroud = getattr(location, "shroud", 0) or 0
        inv.resources += shroud
        ctx.extra["crack_the_case_resources"] = shroud
