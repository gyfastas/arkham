"""Righteous Hunt (Level 1) — Guardian Event. (07109)
<b>交战</b>。选择一名最多2个连接地点远的敌人。移动(一次一个地点)到该敌人的
地点，与其交战，并加入等于该敌人恐惧值数量的[bless]标记到混乱袋。

简化说明：
- 目标敌人自动选择 BFS 距离≤2 内最近的敌人（官方为玩家选择）；会话层可经
  ctx.extra["enemy_instance_id"] 指定。
- 沿途移动为一次性落位（逐地点移动无途中可拦截的引擎窗口，注明）。
- 交战走 ENEMY_ENGAGED 事件（会触发佐伊等"交战时"反应）。
"""

from collections import deque

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import ChaosTokenType, GameEvent, TimingPriority

_RANGE = 2


class RighteousHunt(CardImplementation):
    card_id = "righteous_hunt_lv1"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._bag = None
        self._bus = None

    def bind_chaos_bag(self, bag) -> None:
        self._bag = bag

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def resolve(self, ctx):
        """打出后：移动到2内地敌人处交战，按恐惧值加祝福标记。"""
        if ctx.extra.get("card_id") != self.card_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return

        target_iid = ctx.extra.get("enemy_instance_id")
        if target_iid is None:
            target_iid = self._nearest_enemy_within_range(ctx.game_state, inv)
        target_loc = _enemy_location(ctx.game_state, target_iid)
        if target_loc is None:
            ctx.extra["righteous_hunt_fizzle"] = True
            return
        path = _bfs_path(ctx.game_state, inv.location_id, target_loc)
        if len(path) > _RANGE:
            ctx.extra["righteous_hunt_fizzle"] = True
            return

        enemy = ctx.game_state.get_card_instance(target_iid)
        enemy_data = ctx.game_state.get_card_data(enemy.card_id) if enemy else None
        if enemy is None or enemy_data is None:
            ctx.extra["righteous_hunt_fizzle"] = True
            return

        # 移动到敌人地点（一次一个地点，简化为落位）
        if target_loc != inv.location_id:
            inv.location_id = target_loc

        # 交战（从地点/其他调查员威胁区移入持有者威胁区）
        loc = ctx.game_state.get_location(target_loc)
        if loc is not None and target_iid in loc.enemies:
            loc.enemies.remove(target_iid)
        for other in ctx.game_state.investigators.values():
            if target_iid in other.threat_area:
                other.threat_area.remove(target_iid)
        inv.threat_area.append(target_iid)
        if self._bus is not None:
            from backend.engine.event_bus import EventContext
            self._bus.emit(EventContext(
                game_state=ctx.game_state,
                event=GameEvent.ENEMY_ENGAGED,
                investigator_id=inv.investigator_id,
                enemy_id=target_iid,
            ))

        # 加入等于恐惧值的祝福标记
        added = 0
        if self._bag is not None:
            for _ in range(enemy_data.enemy_horror or 0):
                self._bag.add_token(ChaosTokenType.BLESS)
                added += 1

        ctx.extra["righteous_hunt_target"] = target_iid
        ctx.extra["righteous_hunt_bless_added"] = added
        ctx.game_state.log_effect(
            f"⚔️ 正义猎杀：移动至【{ctx.game_state.card_name(enemy.card_id)}】处交战，"
            f"加入{added}个祝福标记")

    @staticmethod
    def _nearest_enemy_within_range(game_state, inv):
        """BFS 距离≤2 内最近的敌人 instance_id。"""
        dist = {inv.location_id: 0}
        queue = deque([inv.location_id])
        while queue:
            current = queue.popleft()
            if dist[current] > _RANGE:
                break
            loc = game_state.get_location(current)
            if loc is not None and loc.enemies:
                return loc.enemies[0]
            for other in game_state.get_investigators_at_location(current):
                if other.threat_area:
                    return other.threat_area[0]
            for nxt in getattr(loc, "connections", []) or []:
                if nxt in game_state.locations and nxt not in dist:
                    dist[nxt] = dist[current] + 1
                    queue.append(nxt)
        return None


def _enemy_location(game_state, enemy_instance_id) -> str | None:
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
