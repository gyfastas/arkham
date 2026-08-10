"""Under Surveillance (Level 1) — Rogue Event. (07157)
叠加到你所在地点。每个地点限制1张。
强制 - 在一名非[[精英]]敌人进入叠加地点后，丢弃密切监视：自动躲避该敌人
并在叠加地点发现1个线索。该敌人在下一个补给阶段中不准备。

简化说明：
- 叠加关系记录在 scenario.vars["under_surveillance_locations"]
  （{card_instance_key: location_id}，同 hiding_spot/barricade 的 vars
  标记模式）；"每个地点限制1张"在打出时校验。
- "敌人进入地点"经 ENEMY_ENGAGED 捕获（敌人进入地点并与当地点调查员
  交战；敌军阶段猎手移动抵达时引擎发此事件）；敌人生成直接进入地点无
  事件（引擎缺口）。
- "自动躲避"：横置+脱离交战+放置于叠加地点（不发 ENEMY_EVADED，同
  cunning_distraction 从简）；"下个补给阶段不准备"近似为 CARD_READIED
  时重新横置一次（同 jacob_morrison 模式）。
- 事件实现实例在 ROUND_ENDS 被引擎清理，跨轮持续监听缺口同
  barricade_lv0（引擎缺口）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority
from backend.scenarios.official_core import is_elite_enemy

_VARS_KEY = "under_surveillance_locations"


class UnderSurveillance(CardImplementation):
    card_id = "under_surveillance_lv1"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._bus = None
        self._no_ready: str | None = None

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus  # 发现线索需要经事件总线发出 CLUE_DISCOVERED

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def attach_to_location(self, ctx):
        """打出时：叠加到你所在地点（每地点限1张）。"""
        if ctx.extra.get("card_id") != self.card_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        loc_id = inv.location_id
        if ctx.game_state.get_location(loc_id) is None:
            return
        spots = ctx.game_state.scenario.vars.setdefault(_VARS_KEY, {})
        if loc_id in spots.values():
            ctx.game_state.log_effect("👁️ 密切监视：该地点已有密切监视，无法叠加")
            return
        spots[self.instance_id] = loc_id
        ctx.extra["under_surveillance_location"] = loc_id
        ctx.game_state.log_effect("👁️ 密切监视：叠加到所在地点")

    @on_event(GameEvent.ENEMY_ENGAGED, priority=TimingPriority.FORCED)
    def spring_trap(self, ctx):
        """强制 - 非精英敌人进入叠加地点：丢弃本卡，自动躲避+发现1线索。"""
        spots = ctx.game_state.scenario.vars.get(_VARS_KEY, {})
        if self.instance_id not in spots:
            return
        loc_id = spots[self.instance_id]
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or inv.location_id != loc_id:
            return
        enemy_iid = ctx.enemy_id
        enemy = ctx.game_state.get_card_instance(enemy_iid) if enemy_iid else None
        if enemy is None:
            return
        ed = ctx.game_state.get_card_data(enemy.card_id)
        if ed is not None and is_elite_enemy(ed):
            return

        # 丢弃本卡（移除叠加标记）
        spots.pop(self.instance_id, None)

        # 自动躲避：横置+脱离交战+放置于叠加地点
        enemy.exhausted = True
        for other in ctx.game_state.investigators.values():
            if enemy_iid in other.threat_area:
                other.threat_area.remove(enemy_iid)
        loc = ctx.game_state.get_location(loc_id)
        if loc is not None and enemy_iid not in loc.enemies:
            loc.enemies.append(enemy_iid)

        # 在叠加地点发现1个线索
        if loc is not None and loc.clues > 0:
            loc.clues -= 1
            inv.clues += 1
            ctx.extra["under_surveillance_clue"] = True
            if self._bus is not None:
                from backend.engine.event_bus import EventContext
                self._bus.emit(EventContext(
                    game_state=ctx.game_state,
                    event=GameEvent.CLUE_DISCOVERED,
                    investigator_id=inv.investigator_id,
                    location_id=loc_id,
                    amount=1,
                ))
        ctx.game_state.log_effect("👁️ 密切监视：自动躲避敌人并发现1个线索")
        self._no_ready = enemy_iid
        ctx.extra["under_surveillance_evaded"] = enemy_iid

    @on_event(GameEvent.CARD_READIED, priority=TimingPriority.AFTER)
    def suppress_ready(self, ctx):
        """被自动躲避的敌人在下个补给阶段不准备（重新横置一次）。"""
        if self._no_ready is None or ctx.target != self._no_ready:
            return
        enemy = ctx.game_state.get_card_instance(ctx.target)
        if enemy is not None:
            enemy.exhausted = True
            ctx.game_state.log_effect("👁️ 密切监视：敌人在本补给阶段不准备")
        self._no_ready = None
