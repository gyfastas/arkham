"""Look What I Found! (Level 0) — Survivor Event.
快速。在你检定失败后打出。在你所在地点发现2条线索。

简化说明：
- 从手牌中自动触发：你检定失败后自动打出。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class LookWhatIFound(CardImplementation):
    card_id = "look_what_i_found_lv0"

    @on_event(GameEvent.SKILL_TEST_FAILED, priority=TimingPriority.AFTER)
    def discover_two(self, ctx):
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or "look_what_i_found_lv0" not in inv.hand:
            return
        loc = ctx.game_state.get_location(inv.location_id)
        if loc is None:
            return

        # 自动打出
        cd = ctx.game_state.get_card_data("look_what_i_found_lv0")
        cost = getattr(cd, "cost", 2) or 2 if cd else 2
        if inv.resources < cost:
            return
        inv.resources -= cost
        inv.hand.remove("look_what_i_found_lv0")
        inv.discard.append("look_what_i_found_lv0")

        # 发现2条线索（受地点剩余线索限制）
        found = 0
        for _ in range(2):
            if loc.clues > 0:
                loc.clues -= 1
                inv.clues += 1
                found += 1
        ctx.extra["look_what_i_found_clues"] = found
