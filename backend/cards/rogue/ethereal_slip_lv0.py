"""Ethereal Slip (Level 0) — Rogue Event. (08108)
选择连接次数不超过2的已揭示地点的一名非[[精英]]敌人。与该敌人交换位置。

简化说明：
- 目标自动选择：距离2以内已揭示地点的第一个非精英敌人（BFS 顺序，就近
  优先）；可经 ctx.extra["target_enemy_id"] 显式指定（校验非精英、已揭示、
  距离≤2）。官方为玩家自选。
- 交换：敌人移至你当前所在地点（未交战状态——敌人移动后与原交战对象
  解除交战，符合"敌人不随交换保持交战"的通行裁定）；你移至敌人原所在地点。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class EtherealSlip(CardImplementation):
    card_id = "ethereal_slip_lv0"
    max_distance = 2  # lv2 覆盖为 None（任意已揭示地点）

    def _is_elite(self, game_state, enemy_id: str) -> bool:
        enemy = game_state.get_card_instance(enemy_id)
        cd = game_state.get_card_data(enemy.card_id) if enemy else None
        return cd is None or "elite" in (cd.keywords or [])

    def _reachable_locations(self, game_state, start_id: str) -> list[str]:
        """候选地点（不含起点）：lv0 为距离≤2的已揭示地点（BFS 升序）；
        lv2（max_distance=None）为任意已揭示地点，不要求连通。"""
        if self.max_distance is None:
            return [
                loc_id for loc_id, loc in game_state.locations.items()
                if loc_id != start_id and loc.revealed
            ]
        seen = {start_id: 0}
        queue = [start_id]
        order: list[str] = []
        while queue:
            cur = queue.pop(0)
            dist = seen[cur]
            if dist >= self.max_distance:
                continue
            loc = game_state.get_location(cur)
            for nxt in (loc.connections if loc else []) or []:
                if nxt in seen or nxt not in game_state.locations:
                    continue
                seen[nxt] = dist + 1
                nloc = game_state.get_location(nxt)
                if nloc is not None and nloc.revealed:
                    order.append(nxt)
                queue.append(nxt)
        return order

    def _enemies_at(self, game_state, loc_id: str) -> list[str]:
        out: list[str] = []
        loc = game_state.get_location(loc_id)
        if loc is not None:
            out.extend(loc.enemies)
        for inv in game_state.investigators.values():
            if inv.location_id == loc_id:
                out.extend(inv.threat_area)
        return out

    def _find_enemy_location(self, game_state, enemy_id: str) -> str | None:
        for loc in game_state.locations.values():
            if enemy_id in loc.enemies:
                return loc.location_id
        for inv in game_state.investigators.values():
            if enemy_id in inv.threat_area:
                return inv.location_id
        return None

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def swap_places(self, ctx):
        """选择合法敌人并与之交换位置。"""
        if ctx.extra.get("card_id") != self.card_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        my_loc_id = inv.location_id

        target_id = ctx.extra.get("target_enemy_id")
        if target_id is not None:
            # 显式目标：校验非精英、已揭示地点、距离合法
            enemy_loc_id = self._find_enemy_location(ctx.game_state, target_id)
            if enemy_loc_id is None or enemy_loc_id == my_loc_id:
                return
            if self._is_elite(ctx.game_state, target_id):
                return
            if enemy_loc_id not in self._reachable_locations(ctx.game_state, my_loc_id):
                return
        else:
            target_id = None
            enemy_loc_id = None
            for loc_id in self._reachable_locations(ctx.game_state, my_loc_id):
                for eid in self._enemies_at(ctx.game_state, loc_id):
                    if not self._is_elite(ctx.game_state, eid):
                        target_id = eid
                        enemy_loc_id = loc_id
                        break
                if target_id is not None:
                    break
        if target_id is None or enemy_loc_id is None:
            return

        enemy = ctx.game_state.get_card_instance(target_id)
        if enemy is None:
            return

        # 敌人移至你的地点（解除交战，未交战状态）
        for other in ctx.game_state.investigators.values():
            if target_id in other.threat_area:
                other.threat_area.remove(target_id)
        enemy_home = ctx.game_state.get_location(enemy_loc_id)
        if enemy_home is not None and target_id in enemy_home.enemies:
            enemy_home.enemies.remove(target_id)
        my_loc = ctx.game_state.get_location(my_loc_id)
        if my_loc is not None and target_id not in my_loc.enemies:
            my_loc.enemies.append(target_id)

        # 你移至敌人原所在地点
        inv.location_id = enemy_loc_id

        ctx.extra["ethereal_slip_swapped"] = target_id
        ctx.extra["ethereal_slip_moved_to"] = enemy_loc_id
        ctx.game_state.log_effect(
            f"🌀 虚影易位：与【{ctx.game_state.card_name(enemy.card_id)}】交换位置，"
            f"移至【{ctx.game_state.card_name(enemy_loc_id)}】")
