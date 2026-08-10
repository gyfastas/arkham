""""Get behind me!" (Level 0) — Guardian Event. (08021)
快速。在任意[快速]窗口打出。
直到本阶段结束，每当一个敌人将要攻击你所在地点的另一位调查员时，
改为攻击你，然后与你交战。取消每次以此方式进行的攻击所造成的1点恐惧。

简化说明：
- 从手牌中自动触发（官方为玩家选择时机）：敌人阶段敌人攻击同地点另一位
  调查员时，若手牌中有本卡则自动打出（0费），同 heroic_rescue 的约定。
- 打出后效果持续到本阶段结束：本阶段内后续攻击同地点其他调查员的敌人
  同样被转移（不再重复打出）。
- 转移的攻击直接增减持有者的伤害/恐惧（未经分配/取消窗口，与
  heroic_rescue 一致，注明）；其中恐惧先取消1点（下限0）。
- 敌人随后被移动到你的威胁区（"与你交战"），并发出 ENEMY_ENGAGED。
"""

from backend.cards._shared import find_holder
from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class GetBehindMe(CardImplementation):
    card_id = "get_behind_me_lv0"
    persistent_in_hand = True  # 手牌中持续监听敌人攻击

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._bus = None
        self._armed_for: str | None = None  # 本阶段内效果持有者

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus

    @on_event(GameEvent.ENEMY_ATTACKS, priority=TimingPriority.WHEN)
    def redirect_attack(self, ctx):
        """敌人攻击同地点另一位调查员：改为攻击持有者并与之交战。"""
        target = ctx.game_state.get_investigator(ctx.investigator_id)
        if target is None:
            return
        holder = ctx.game_state.get_investigator(self._armed_for) \
            if self._armed_for else find_holder(ctx.game_state, self.card_id)
        if holder is None or holder.investigator_id == target.investigator_id:
            return
        if holder.location_id != target.location_id:
            return
        enemy_iid = ctx.enemy_id
        enemy_data = None
        if enemy_iid:
            enemy = ctx.game_state.get_card_instance(enemy_iid)
            if enemy is not None:
                enemy_data = ctx.game_state.get_card_data(enemy.card_id)
        if enemy_data is None:
            return

        if self._armed_for is None:
            # 尚未打出：自动打出（0费）
            data = ctx.game_state.get_card_data(self.card_id)
            cost = (getattr(data, "cost", 0) or 0) if data else 0
            if holder.resources < cost:
                return
            holder.resources -= cost
            holder.hand.remove(self.card_id)
            holder.discard.append(self.card_id)
            self._armed_for = holder.investigator_id
            ctx.game_state.log_effect(
                "🛡️ 站到我身后！：本阶段内代为承受同地点其他调查员受到的攻击")

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

        # 结算攻击：取消其中1点恐惧（下限0）
        horror = max(0, (enemy_data.enemy_horror or 0) - 1)
        holder.damage += enemy_data.enemy_damage or 0
        holder.horror += horror
        ctx.extra["get_behind_me_redirected"] = enemy_iid
        if holder.is_defeated and self._bus is not None:
            from backend.engine.event_bus import EventContext
            self._bus.emit(EventContext(
                game_state=ctx.game_state,
                event=GameEvent.INVESTIGATOR_DEFEATED,
                investigator_id=holder.investigator_id,
            ))

    @on_event(GameEvent.INVESTIGATION_PHASE_ENDS, priority=TimingPriority.AFTER)
    @on_event(GameEvent.ENEMY_PHASE_ENDS, priority=TimingPriority.AFTER)
    @on_event(GameEvent.MYTHOS_PHASE_ENDS, priority=TimingPriority.AFTER)
    @on_event(GameEvent.UPKEEP_PHASE_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        self._armed_for = None
