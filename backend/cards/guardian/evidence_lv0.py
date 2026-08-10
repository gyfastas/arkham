"""Evidence! (Level 0) — Guardian Event.
快速。在你击败一名敌人后打出。发现你所在地点的1条线索。

简化说明：
- "在你击败一名敌人后打出"的快速窗口由会话层控制；打出后经由
  CARD_PLAYED 结算效果（与 dynamite_blast 同一模式）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class Evidence(CardImplementation):
    card_id = "evidence_lv0"

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def discover_clue(self, ctx):
        """打出后：发现你所在地点的1条线索。"""
        if ctx.extra.get("card_id") != "evidence_lv0":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        location = ctx.game_state.get_location(inv.location_id)
        if location and location.clues > 0:
            location.clues -= 1
            inv.clues += 1
            ctx.extra["evidence_clue_discovered"] = True
