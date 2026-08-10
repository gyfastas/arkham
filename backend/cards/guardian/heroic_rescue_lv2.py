"""Heroic Rescue (Level 2) — Guardian Event. (06234)
快速。在一个非精英敌人将要攻击你所在地点或一个连接地点的另一位调查员时打出。
如果你不在该地点，移动到该地点。与该敌人交战并改为你结算它的攻击。
然后，对其造成1点伤害。

简化说明：
- 从手牌中自动触发（官方为玩家选择时机）：敌人阶段非精英敌人攻击你所在
  地点或连接地点的另一位调查员时自动打出（0费），同 heroic_rescue_lv0。
- 持有者先移动到目标地点（不经 MOVE 行动/趁乱攻击，直接改 location_id）。
- 攻击直接增减持有者的伤害/恐惧（未经分配/取消窗口，同 lv0，注明）。
- 反打1点伤害经 _shared.deal_damage_to_enemy 结算（含击败流程）。
"""

from backend.cards._shared import deal_damage_to_enemy, find_holder
from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class HeroicRescueLv2(CardImplementation):
    card_id = "heroic_rescue_lv2"
    persistent_in_hand = True  # 手牌中持续监听敌人攻击

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._bus = None

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus

    @on_event(GameEvent.ENEMY_ATTACKS, priority=TimingPriority.WHEN)
    def intercept_attack(self, ctx):
        """非精英敌人攻击你/连接地点的另一调查员：移动过去代为承受并反打1点。"""
        target = ctx.game_state.get_investigator(ctx.investigator_id)
        if target is None:
            return
        holder = find_holder(ctx.game_state, self.card_id)
        if holder is None or holder.investigator_id == target.investigator_id:
            return
        # 你所在地点或连接地点
        holder_loc = ctx.game_state.get_location(holder.location_id)
        reachable = {holder.location_id} | set(
            getattr(holder_loc, "connections", []) or [])
        if target.location_id not in reachable:
            return
        enemy_iid = ctx.enemy_id
        enemy = ctx.game_state.get_card_instance(enemy_iid) if enemy_iid else None
        enemy_data = ctx.game_state.get_card_data(enemy.card_id) if enemy else None
        if enemy is None or enemy_data is None:
            return
        if "elite" in (enemy_data.keywords or []):
            return
        data = ctx.game_state.get_card_data(self.card_id)
        cost = (getattr(data, "cost", 0) or 0) if data else 0
        if holder.resources < cost:
            return

        # 从手牌打出（支付费用）
        holder.resources -= cost
        holder.hand.remove(self.card_id)
        holder.discard.append(self.card_id)

        # 移动到目标地点（若不在）
        if holder.location_id != target.location_id:
            holder.location_id = target.location_id
            ctx.game_state.log_effect(
                f"🛡️ 英勇救援：移动到【{ctx.game_state.card_name(target.location_id)}】")

        # 取消原攻击，改为与持有者交战并结算对持有者的攻击
        ctx.cancel()
        if enemy_iid in target.threat_area:
            target.threat_area.remove(enemy_iid)
        for loc in ctx.game_state.locations.values():
            if enemy_iid in loc.enemies:
                loc.enemies.remove(enemy_iid)
        if enemy_iid not in holder.threat_area:
            holder.threat_area.append(enemy_iid)
        if self._bus is not None:
            from backend.engine.event_bus import EventContext
            self._bus.emit(EventContext(
                game_state=ctx.game_state,
                event=GameEvent.ENEMY_ENGAGED,
                investigator_id=holder.investigator_id,
                enemy_id=enemy_iid,
            ))

        holder.damage += enemy_data.enemy_damage or 0
        holder.horror += enemy_data.enemy_horror or 0
        ctx.game_state.log_effect(
            f"🛡️ 英勇救援：代为承受【{ctx.game_state.card_name(enemy.card_id)}】的攻击")
        if holder.is_defeated and self._bus is not None:
            from backend.engine.event_bus import EventContext
            self._bus.emit(EventContext(
                game_state=ctx.game_state,
                event=GameEvent.INVESTIGATOR_DEFEATED,
                investigator_id=holder.investigator_id,
            ))

        # 然后对该敌人造成1点伤害
        deal_damage_to_enemy(
            ctx.game_state, self._bus, enemy_iid, 1,
            defeated_by=holder.investigator_id,
        )
        ctx.extra["heroic_rescue_target"] = enemy_iid
