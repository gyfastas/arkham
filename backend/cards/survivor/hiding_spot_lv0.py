"""Hiding Spot (Level 0) — Survivor Event.
快速。将藏身地点叠加到任意一个地点。
被叠加地点上每名非精英敌人获得冷漠。
强制 - 当敌军阶段结束时，如果该地点上有准备的敌人：丢弃藏身地点。

简化说明：
- 附加关系记录在 scenario.vars["hiding_spot_locations"]（同 barricade 的
  vars 标记模式）；目标地点默认为打出者所在地点，可经
  ctx.extra["location_id"] 指定（官方可叠加任意地点，需选择 UI）。
- "非精英敌人获得冷漠"：引擎当前无任何消费 aloof 关键词的机制（交战限制
  未实现），仅保留地点标记供后续引擎接入（引擎缺口，见报告）。
- 强制弃牌挂 ENEMY_PHASE_ENDS：该地点存在未横置敌人（含与当地点调查员
  交战的）即移除标记。
- 跨轮持续：事件实现实例在 ROUND_ENDS 被引擎清理，跨轮监听缺口同
  barricade_lv0（见报告）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class HidingSpot(CardImplementation):
    card_id = "hiding_spot_lv0"

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def attach_to_location(self, ctx):
        """打出时：叠加到目标地点（默认你所在地点）。"""
        if ctx.extra.get("card_id") != self.card_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        loc_id = ctx.extra.get("location_id") or inv.location_id
        if ctx.game_state.get_location(loc_id) is None:
            return
        spots = ctx.game_state.scenario.vars.setdefault("hiding_spot_locations", [])
        if loc_id not in spots:
            spots.append(loc_id)
        ctx.extra["hiding_spot_location"] = loc_id
        ctx.game_state.log_effect(
            "🫥 藏身地点：叠加到目标地点，该地点非精英敌人获得冷漠")

    @on_event(GameEvent.ENEMY_PHASE_ENDS, priority=TimingPriority.AFTER)
    def forced_discard(self, ctx):
        """强制 - 敌军阶段结束时，被叠加地点上有准备的敌人：丢弃藏身地点。"""
        spots = ctx.game_state.scenario.vars.get("hiding_spot_locations", [])
        if not spots:
            return
        for loc_id in list(spots):
            if self._has_ready_enemy_at(ctx, loc_id):
                spots.remove(loc_id)
                ctx.extra["hiding_spot_discarded"] = loc_id
                ctx.game_state.log_effect(
                    "🫥 藏身地点：地点上有准备的敌人，藏身地点被丢弃")

    @staticmethod
    def _has_ready_enemy_at(ctx, location_id) -> bool:
        """该地点是否有未横置的敌人（未交战的 + 与当地点调查员交战的）。"""
        loc = ctx.game_state.get_location(location_id)
        if loc is not None:
            for enemy_iid in loc.enemies:
                enemy = ctx.game_state.get_card_instance(enemy_iid)
                if enemy is not None and not enemy.exhausted:
                    return True
        for inv in ctx.game_state.investigators.values():
            if inv.location_id != location_id:
                continue
            for enemy_iid in inv.threat_area:
                enemy = ctx.game_state.get_card_instance(enemy_iid)
                if enemy is not None and not enemy.exhausted:
                    return True
        return False
