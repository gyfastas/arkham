"""The Truth Beckons (Level 0) — Seeker Event. (07154)
只能在你未与敌人交战时打出。
移动。选择一个未揭示地点。朝向该地点最短的路径移动(一次一个地点)，
直到你进入该地点。如果你翻开了地点，或与敌人交战，或你的移动被
阻挡，结束此效果。

简化说明：
- 目标选择：ctx.extra["target_location_id"] 指定；缺省自动选择经连接
  可达的最近未揭示地点（BFS 最短路径）；
- 逐地点移动简化为直接传送至路径终点：路径上第一个未揭示地点（含目标
  本身，进入未揭示地点即翻开并结束效果）；路径全为已揭示时移动到目标；
- 中途敌人交战/移动被特殊效果阻挡无引擎事件可循（引擎缺口），仅校验
  打出时未交战、路径存在。
"""

from collections import deque

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class TheTruthBeckons(CardImplementation):
    card_id = "the_truth_beckons_lv0"

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def move_toward(self, ctx):
        if ctx.extra.get("card_id") != self.card_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        # 只能在你未与敌人交战时打出
        if ctx.game_state.get_engaged_enemies(inv.investigator_id):
            ctx.extra["truth_beckons_failed"] = "engaged"
            return

        start = ctx.game_state.get_location(inv.location_id)
        if start is None:
            return

        target_id = ctx.extra.get("target_location_id")
        if target_id is None:
            target_id = self._nearest_unrevealed(ctx, start.location_id)
        if target_id is None:
            ctx.extra["truth_beckons_failed"] = "no_path"
            return

        path = self._shortest_path(ctx, start.location_id, target_id)
        if not path:
            ctx.extra["truth_beckons_failed"] = "no_path"
            return

        # 逐地点前进：进入第一个未揭示地点即翻开并结束效果
        final = start.location_id
        for loc_id in path:
            loc = ctx.game_state.get_location(loc_id)
            if loc is None:
                break  # 移动被阻挡
            final = loc_id
            if not loc.revealed:
                loc.revealed = True  # 进入即翻开（场景层效果不在此模拟）
                break
        if final == start.location_id:
            ctx.extra["truth_beckons_failed"] = "blocked"
            return
        inv.location_id = final
        ctx.extra["truth_beckons_moved"] = final
        ctx.game_state.log_effect(
            f"🚪 真相的呼唤：沿最短路径移动到"
            f"【{ctx.game_state.card_name(final)}】")

    @staticmethod
    def _shortest_path(ctx, start_id: str, target_id: str) -> list[str]:
        """BFS 最短路径（不含起点，含终点）；不可达返回空。"""
        if start_id == target_id:
            return []
        visited = {start_id}
        queue = deque([(start_id, [])])
        while queue:
            current, path = queue.popleft()
            loc = ctx.game_state.get_location(current)
            for nxt in (loc.connections if loc is not None else []) or []:
                if nxt in visited:
                    continue
                visited.add(nxt)
                new_path = path + [nxt]
                if nxt == target_id:
                    return new_path
                queue.append((nxt, new_path))
        return []

    def _nearest_unrevealed(self, ctx, start_id: str) -> str | None:
        """最近的可达未揭示地点（BFS 顺序即距离序）。"""
        visited = {start_id}
        queue = deque([start_id])
        while queue:
            current = queue.popleft()
            loc = ctx.game_state.get_location(current)
            for nxt in (loc.connections if loc is not None else []) or []:
                if nxt in visited:
                    continue
                visited.add(nxt)
                nloc = ctx.game_state.get_location(nxt)
                if nloc is None:
                    continue
                if not nloc.revealed:
                    return nxt
                queue.append(nxt)
        return None
