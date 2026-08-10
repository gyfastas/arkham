"""On the Trail (Level 1) — Guardian Event. (08084)
选择一个不在你所在地点的敌人。向该敌人移动两次，或在你与所选敌人之间
最短路径上的任意一个空地点发现1条线索。

简化说明：
- 目标自动选择：离你最近（BFS最短路径）的其他地点敌人；可经
  ctx.extra["enemy_instance_id"] 指定。
- 模式经 ctx.extra["mode"]（"move"/"clue"）指定，默认 "move"。
- "移动两次"：沿最短路径移动至多2步（可进入目标所在地点；不经 MOVE
  行动/趁乱攻击，直接改 location_id，同 heroic_rescue_lv2 的约定）。
- "空地点"：采用"没有敌人"的工作定义（发现线索要求该地点有线索可取；
  官方"empty"定义存在解释空间，注明）。自动选择路径上第一个有线索的
  空地点（可经 ctx.extra["clue_location_id"] 指定）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import CardType, GameEvent, TimingPriority


def _bfs_path(game_state, start: str, goal: str) -> list[str] | None:
    """start 到 goal 的最短路径（含两端）；不可达返回 None。"""
    if start == goal:
        return [start]
    visited = {start}
    parent: dict[str, str] = {}
    queue = [start]
    while queue:
        current = queue.pop(0)
        loc = game_state.get_location(current)
        if loc is None:
            continue
        for conn in loc.connections:
            if conn in visited:
                continue
            visited.add(conn)
            parent[conn] = current
            if conn == goal:
                path = [goal]
                while path[-1] != start:
                    path.append(parent[path[-1]])
                return list(reversed(path))
            queue.append(conn)
    return None


class OnTheTrail(CardImplementation):
    card_id = "on_the_trail_lv1"

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def resolve(self, ctx):
        if ctx.extra.get("card_id") != self.card_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return

        enemy_iid, enemy_loc = self._find_target(ctx, inv)
        if enemy_iid is None or enemy_loc is None:
            ctx.extra["on_the_trail_fizzle"] = True
            ctx.game_state.log_effect("🐾 寻迹：其他地点没有敌人，效果不结算")
            return

        path = _bfs_path(ctx.game_state, inv.location_id, enemy_loc)
        if not path or len(path) < 2:
            ctx.extra["on_the_trail_fizzle"] = True
            return

        mode = ctx.extra.get("mode") or "move"
        if mode == "clue":
            self._discover_clue(ctx, inv, path)
        else:
            self._move_toward(ctx, inv, path)
        ctx.extra["on_the_trail_enemy"] = enemy_iid

    def _find_target(self, ctx, inv):
        """目标敌人与其地点：extra 指定，否则 BFS 最近的其他地点敌人。"""
        enemy_iid = ctx.extra.get("enemy_instance_id")
        if enemy_iid is not None:
            loc = self._enemy_location(ctx, enemy_iid)
            if loc is not None and loc != inv.location_id:
                return enemy_iid, loc
            return None, None

        # BFS 按距离枚举敌人
        visited = {inv.location_id}
        queue = [inv.location_id]
        while queue:
            current = queue.pop(0)
            loc = ctx.game_state.get_location(current)
            if loc is None:
                continue
            if current != inv.location_id:
                found = self._enemy_at(ctx, current)
                if found is not None:
                    return found, current
            for conn in loc.connections:
                if conn not in visited:
                    visited.add(conn)
                    queue.append(conn)
        return None, None

    @staticmethod
    def _enemy_at(ctx, location_id) -> str | None:
        """地点上的第一个敌人（未交战列表 + 当地调查员威胁区）。"""
        loc = ctx.game_state.get_location(location_id)
        if loc is not None and loc.enemies:
            for iid in loc.enemies:
                data = ctx.game_state.get_card_data(
                    getattr(ctx.game_state.get_card_instance(iid), "card_id", ""))
                if data is not None and data.type == CardType.ENEMY:
                    return iid
        for other in ctx.game_state.get_investigators_at_location(location_id):
            for iid in other.threat_area:
                data = ctx.game_state.get_card_data(
                    getattr(ctx.game_state.get_card_instance(iid), "card_id", ""))
                if data is not None and data.type == CardType.ENEMY:
                    return iid
        return None

    @staticmethod
    def _enemy_location(ctx, enemy_iid) -> str | None:
        for loc in ctx.game_state.locations.values():
            if enemy_iid in loc.enemies:
                return loc.location_id
        for other in ctx.game_state.investigators.values():
            if enemy_iid in other.threat_area:
                return other.location_id
        return None

    def _move_toward(self, ctx, inv, path) -> None:
        """沿最短路径移动至多2步。"""
        steps = min(2, len(path) - 1)
        destination = path[steps]
        inv.location_id = destination
        ctx.extra["on_the_trail_moved"] = destination
        ctx.game_state.log_effect(
            f"🐾 寻迹：向敌人移动{steps}步至【{ctx.game_state.card_name(destination)}】")

    def _discover_clue(self, ctx, inv, path) -> None:
        """在路径之间（不含两端）的第一个有线索空地点发现1条线索。"""
        between = path[1:-1]
        target_loc = None
        wanted = ctx.extra.get("clue_location_id")
        for loc_id in between:
            loc = ctx.game_state.get_location(loc_id)
            if loc is None or loc.clues <= 0:
                continue
            if self._enemy_at(ctx, loc_id) is not None:
                continue  # 非空地点（有敌人）
            if wanted is not None and loc_id != wanted:
                continue
            target_loc = loc
            break
        if target_loc is None:
            ctx.extra["on_the_trail_fizzle"] = True
            ctx.game_state.log_effect("🐾 寻迹：路径之间没有可取线索的空地点")
            return
        target_loc.clues -= 1
        inv.clues += 1
        ctx.extra["on_the_trail_clue"] = target_loc.location_id
        ctx.game_state.log_effect(
            f"🐾 寻迹：在【{ctx.game_state.card_name(target_loc.location_id)}】发现1条线索")
