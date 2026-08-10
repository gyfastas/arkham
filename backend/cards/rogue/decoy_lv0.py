"""Decoy (Level 0) — Rogue Event. (05234)
躲避。自动躲避你所在地点的一名非[[精英]]敌人。
[反应]在你打出诱敌时，提升其费用2点：将"一名非[[精英]]敌人"变为"最多2名
非[[精英]]敌人"。
[反应]在你打出诱敌时，提升其费用2点：将"你所在地点"变为"1个与你所在地点
之间连接次数不超过2的地点"。

简化说明：
- 基础效果自动结算：躲避（横置、解除交战、放回其所在地点并发出
  ENEMY_EVADED，cheap_shot 同例）你所在地点的第一个非精英敌人；目标可经
  ctx.extra["decoy_target_ids"]（list）显式指定。
- 两个[反应]加费升级为玩家可选项，默认不启用；可经
  ctx.extra["decoy_boost_targets"]（最多2名）与
  ctx.extra["decoy_boost_range"]（至多2连接距离）启用，每项额外+2资源
  （打出时引擎已扣基础费用，此处补扣差额；资源不足则忽略该升级）。
- 目标自动选择为合法范围内的前N个非精英敌人（官方为玩家自选）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority

_BOOST_COST = 2


class Decoy(CardImplementation):
    card_id = "decoy_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._bus = None

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus

    def _is_elite(self, game_state, enemy_id: str) -> bool:
        enemy = game_state.get_card_instance(enemy_id)
        cd = game_state.get_card_data(enemy.card_id) if enemy else None
        return cd is None or "elite" in (cd.keywords or [])

    def _locations_within(self, game_state, start_id: str, max_dist: int) -> list[str]:
        """BFS：距 start 至多 max_dist 连接的地点（含起点）。"""
        seen = {start_id: 0}
        queue = [start_id]
        while queue:
            cur = queue.pop(0)
            if seen[cur] >= max_dist:
                continue
            loc = game_state.get_location(cur)
            for nxt in (loc.connections if loc else []) or []:
                if nxt not in seen and nxt in game_state.locations:
                    seen[nxt] = seen[cur] + 1
                    queue.append(nxt)
        return list(seen.keys())

    def _evade_enemy(self, game_state, inv, enemy_id: str, home_loc_id: str) -> bool:
        """复刻引擎躲避成功结算：横置、解除交战、放回其所在地点并发事件。"""
        enemy = game_state.get_card_instance(enemy_id)
        if enemy is None:
            return False
        enemy.exhausted = True
        for other in game_state.investigators.values():
            if enemy_id in other.threat_area:
                other.threat_area.remove(enemy_id)
        home = game_state.get_location(home_loc_id)
        if home is not None and enemy_id not in home.enemies:
            home.enemies.append(enemy_id)
        if self._bus is not None:
            from backend.engine.event_bus import EventContext
            self._bus.emit(EventContext(
                game_state=game_state,
                event=GameEvent.ENEMY_EVADED,
                investigator_id=inv.investigator_id,
                enemy_id=enemy_id,
            ))
        game_state.log_effect(
            f"🎏 诱敌：自动躲避【{game_state.card_name(enemy.card_id)}】")
        return True

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def auto_evade(self, ctx):
        """自动躲避非精英敌人（可经 extra 升级数量/范围）。"""
        if ctx.extra.get("card_id") != self.card_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return

        # 升级：补扣加费（资源不足则忽略对应升级）
        boost_targets = bool(ctx.extra.get("decoy_boost_targets"))
        boost_range = bool(ctx.extra.get("decoy_boost_range"))
        if boost_targets:
            if inv.resources >= _BOOST_COST:
                inv.resources -= _BOOST_COST
            else:
                boost_targets = False
        if boost_range:
            if inv.resources >= _BOOST_COST:
                inv.resources -= _BOOST_COST
            else:
                boost_range = False

        max_targets = 2 if boost_targets else 1
        if boost_range:
            loc_ids = self._locations_within(ctx.game_state, inv.location_id, 2)
        else:
            loc_ids = [inv.location_id]

        # 目标：extra 指定或自动（范围内前N个非精英）
        requested = ctx.extra.get("decoy_target_ids") or []
        candidates: list[tuple[str, str]] = []  # (enemy_id, home_loc_id)
        for loc_id in loc_ids:
            loc = ctx.game_state.get_location(loc_id)
            enemies: list[str] = []
            if loc is not None:
                enemies.extend(loc.enemies)
            for other in ctx.game_state.investigators.values():
                if other.location_id == loc_id:
                    enemies.extend(other.threat_area)
            for eid in enemies:
                if eid in [c[0] for c in candidates]:
                    continue
                if self._is_elite(ctx.game_state, eid):
                    continue
                if requested and eid not in requested:
                    continue
                candidates.append((eid, loc_id))

        evaded: list[str] = []
        for eid, home_loc in candidates[:max_targets]:
            if self._evade_enemy(ctx.game_state, inv, eid, home_loc):
                evaded.append(eid)
        if evaded:
            ctx.extra["decoy_evaded"] = evaded
