"""Scout Ahead (Level 0) — Rogue Event. (08047)
移动。移动最多3次。这次移动中敌人不会与你交战。

简化说明：
- 移动路径自动选择：沿连接地点前进最多3步，不回退到上一地点（官方为
  玩家逐步选择目的地）；可用 ctx.extra["destinations"] 显式给定逐步
  目的地列表（按顺序校验连接关系，最多3步）。
- "敌人不会与你交战"：引擎的移动流程本就不会触发交战（交战仅发生在
  敌军阶段），该限制天然满足。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority

_MAX_MOVES = 3


class ScoutAhead(CardImplementation):
    card_id = "scout_ahead_lv0"

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def move_up_to_three(self, ctx):
        if ctx.extra.get("card_id") != self.card_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return

        destinations = ctx.extra.get("destinations")
        if destinations is None:
            destinations = self._auto_route(ctx, inv)

        moved = []
        for dest_id in list(destinations)[:_MAX_MOVES]:
            cur = ctx.game_state.get_location(inv.location_id)
            if cur is None or dest_id not in cur.connections:
                break
            if ctx.game_state.get_location(dest_id) is None:
                break
            inv.location_id = dest_id
            moved.append(dest_id)
        if moved:
            ctx.extra["scout_ahead_moved"] = moved
            ctx.game_state.log_effect(
                f"🧭 侦察前路：连续移动{len(moved)}次至【{ctx.game_state.card_name(moved[-1])}】，"
                "移动中敌人不与你交战")

    @staticmethod
    def _auto_route(ctx, inv) -> list[str]:
        """默认路线：每步走向第一个非上一地点的连接地点，最多3步。"""
        route = []
        current = inv.location_id
        previous = None
        for _ in range(_MAX_MOVES):
            loc = ctx.game_state.get_location(current)
            if loc is None:
                break
            options = [c for c in (loc.connections or [])
                       if c != previous and ctx.game_state.get_location(c) is not None]
            if not options:
                break
            nxt = options[0]
            route.append(nxt)
            previous, current = current, nxt
        return route
