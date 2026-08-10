"""Small Favor (Level 0) — Rogue Event. (05277)
对你所在地点的一名非[[精英]]敌人造成1点伤害。
[reaction] 在你打出帮个小忙时，提升其费用2点：将"造成1点伤害"变为"造成2点伤害"。
[reaction] 在你打出帮个小忙时，提升其费用2点：将"你所在地点"变为"1个与你所在
地点之间连接次数不超过2的地点"。

简化说明：
- 两个增费反应自动决定：本地点有可伤目标且资源≥2时自动+2造成2点伤害；
  本地点无目标且资源≥2时自动+2扩大范围（广度优先搜索2步连接内的第一个
  非精英敌人）。可用 ctx.extra["boost_damage"]/["boost_range"]=False 关闭，
  或用 ctx.extra["target_enemy_id"] 显式指定目标（官方均为玩家选择，
  同 watch_this 的自动花费先例）。
- 伤害/击败经 _shared.deal_damage_to_enemy 结算（ENEMY_DEFEATED 带击败者）。
"""

from backend.cards._shared import deal_damage_to_enemy
from backend.cards.base import CardImplementation, on_event
from backend.models.enums import CardType, GameEvent, TimingPriority
from backend.scenarios.official_core import is_elite_enemy

_BOOST_COST = 2


class SmallFavor(CardImplementation):
    card_id = "small_favor_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._bus = None

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus  # 击败敌人需要经事件总线发出 ENEMY_DEFEATED

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def deal_damage(self, ctx):
        if ctx.extra.get("card_id") != self.card_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return

        # 目标池：你所在地点的非精英敌人（地点上的 + 与当地点调查员交战的）
        candidates = self._enemies_at(ctx, inv.location_id)
        target_id = ctx.extra.get("target_enemy_id")

        # 增费分支1：造成2点伤害
        boost_damage = ctx.extra.get("boost_damage")
        if boost_damage is None:
            boost_damage = bool(candidates or target_id) and inv.resources >= _BOOST_COST
        if boost_damage and inv.resources >= _BOOST_COST:
            inv.resources -= _BOOST_COST
            ctx.extra["small_favor_boost_damage"] = True
        else:
            boost_damage = False

        # 增费分支2：范围扩至2步连接内
        if not candidates and target_id is None:
            boost_range = ctx.extra.get("boost_range")
            if boost_range is None:
                boost_range = inv.resources >= _BOOST_COST
            if boost_range and inv.resources >= _BOOST_COST:
                far = self._enemies_within_range(ctx, inv.location_id, 2)
                if far:
                    inv.resources -= _BOOST_COST
                    ctx.extra["small_favor_boost_range"] = True
                    candidates = far

        if target_id is None:
            if not candidates:
                return
            target_id = candidates[0]
        elif target_id not in candidates and not ctx.extra.get("small_favor_boost_range"):
            # 显式目标必须在当前合法目标池中
            if target_id not in self._enemies_at(ctx, inv.location_id):
                return

        damage = 2 if boost_damage else 1
        defeated = deal_damage_to_enemy(
            ctx.game_state, self._bus, target_id, damage,
            defeated_by=ctx.investigator_id,
        )
        ctx.extra["small_favor_target"] = target_id
        ctx.extra["small_favor_damage"] = damage
        if defeated:
            ctx.extra["small_favor_defeated"] = target_id
        ctx.game_state.log_effect(f"🤝 帮个小忙：造成{damage}点伤害")

    @staticmethod
    def _is_valid_enemy(ctx, enemy_iid: str) -> bool:
        inst = ctx.game_state.get_card_instance(enemy_iid)
        if inst is None:
            return False
        ed = ctx.game_state.get_card_data(inst.card_id)
        return (
            ed is not None
            and ed.type == CardType.ENEMY
            and not is_elite_enemy(ed)
        )

    @classmethod
    def _enemies_at(cls, ctx, location_id: str) -> list[str]:
        """该地点的非精英敌人（未交战的 + 与当地点调查员交战的）。"""
        loc = ctx.game_state.get_location(location_id)
        if loc is None:
            return []
        pool = list(loc.enemies)
        for inv in ctx.game_state.get_investigators_at_location(location_id):
            pool.extend(inv.threat_area)
        seen, out = set(), []
        for eid in pool:
            if eid in seen:
                continue
            seen.add(eid)
            if cls._is_valid_enemy(ctx, eid):
                out.append(eid)
        return out

    @classmethod
    def _enemies_within_range(cls, ctx, location_id: str, max_hops: int) -> list[str]:
        """广度优先：连接次数不超过 max_hops 的地点上的非精英敌人。"""
        visited = {location_id}
        frontier = [location_id]
        for _ in range(max_hops):
            nxt = []
            for loc_id in frontier:
                loc = ctx.game_state.get_location(loc_id)
                if loc is None:
                    continue
                for conn in loc.connections or []:
                    if conn not in visited and ctx.game_state.get_location(conn) is not None:
                        visited.add(conn)
                        nxt.append(conn)
            frontier = nxt
        out = []
        for loc_id in sorted(visited - {location_id}):
            out.extend(cls._enemies_at(ctx, loc_id))
        return out
