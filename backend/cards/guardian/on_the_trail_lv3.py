"""On the Trail (Level 3) — Guardian Event. (08085)
选择你所在地点以外任何地点的一名敌人。朝该敌人移动2次。
在每个你因此效果进入的地点各发现1个线索。

简化说明：
- 目标敌人自动选择 BFS 距离最近的敌人（官方为玩家选择）；会话层可经
  ctx.extra["enemy_instance_id"] 指定其他地点的敌人。
- "朝该敌人移动2次"沿 BFS 最短路径至多移动2步（路径不足2步则走完全程）。
- 进入的每个地点发现1条线索（地点无线索时不欠费）。
"""

from collections import deque

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class OnTheTrail(CardImplementation):
    card_id = "on_the_trail_lv3"

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def resolve(self, ctx):
        """打出后：朝选定敌人移动至多2步，每个进入的地点发现1线索。"""
        if ctx.extra.get("card_id") != self.card_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return

        target_iid = ctx.extra.get("enemy_instance_id")
        if target_iid is None:
            target_iid = self._nearest_enemy(ctx.game_state, inv)
        target_loc = _enemy_location(ctx.game_state, target_iid)
        if target_loc is None or target_loc == inv.location_id:
            ctx.extra["on_the_trail_fizzle"] = True
            return

        path = _bfs_path(ctx.game_state, inv.location_id, target_loc)
        entered = []
        for loc_id in path[:2]:
            inv.location_id = loc_id
            entered.append(loc_id)
            loc = ctx.game_state.get_location(loc_id)
            if loc is not None and loc.clues > 0:
                loc.clues -= 1
                inv.clues += 1

        ctx.extra["on_the_trail_path"] = entered
        ctx.game_state.log_effect(
            f"🐾 追踪：朝【{ctx.game_state.card_name(ctx.game_state.get_card_instance(target_iid).card_id)}】"
            f"移动{len(entered)}次，沿途发现{len(entered)}条线索"
            if entered else "🐾 追踪：未能移动")

    @staticmethod
    def _nearest_enemy(game_state, inv):
        """BFS 找最近的有敌人的地点，返回其中一个敌人 instance_id。"""
        dist = {inv.location_id: 0}
        queue = deque([inv.location_id])
        while queue:
            current = queue.popleft()
            if current != inv.location_id:
                loc = game_state.get_location(current)
                if loc is not None and loc.enemies:
                    return loc.enemies[0]
                for other in game_state.get_investigators_at_location(current):
                    if other.threat_area:
                        return other.threat_area[0]
            loc = game_state.get_location(current)
            for nxt in getattr(loc, "connections", []) or []:
                if nxt in game_state.locations and nxt not in dist:
                    dist[nxt] = dist[current] + 1
                    queue.append(nxt)
        return None


def _enemy_location(game_state, enemy_instance_id) -> str | None:
    """敌人所在地点：未交战查地点列表，交战查持有者地点。"""
    if enemy_instance_id is None:
        return None
    for loc in game_state.locations.values():
        if enemy_instance_id in loc.enemies:
            return loc.location_id
    for inv in game_state.investigators.values():
        if enemy_instance_id in inv.threat_area:
            return inv.location_id
    return None


def _bfs_path(game_state, start: str, goal: str) -> list[str]:
    """start→goal 的最短路径（不含 start，含 goal）；不可达返回 []。"""
    if start == goal:
        return []
    parent = {start: None}
    queue = deque([start])
    while queue:
        current = queue.popleft()
        loc = game_state.get_location(current)
        for nxt in getattr(loc, "connections", []) or []:
            if nxt in parent or nxt not in game_state.locations:
                continue
            parent[nxt] = current
            if nxt == goal:
                path = [nxt]
                while parent[path[0]] is not None:
                    path.insert(0, parent[path[0]])
                return path[1:]  # 去掉起点
            queue.append(nxt)
    return []
