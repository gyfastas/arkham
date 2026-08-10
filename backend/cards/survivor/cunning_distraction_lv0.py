"""Cunning Distraction (Level 0) — Survivor Event.
Evade. Automatically evade all enemies at your location.

简化说明：
- 自动躲避=横置+脱离交战并留在当前地点，不移动调查员。
- 不触发 ENEMY_EVADED 事件（与 stray_cat 等"自动躲避"实现一致，从简）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class CunningDistraction(CardImplementation):
    card_id = "cunning_distraction_lv0"

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def evade_all(self, ctx):
        """自动躲避你所在地点的所有敌人（含与其他调查员交战的）。"""
        if ctx.extra.get("card_id") != "cunning_distraction_lv0":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        loc = ctx.game_state.get_location(inv.location_id)
        if loc is None:
            return

        evaded = []
        # 脱离交战敌人（任何调查员的威胁区，只要该调查员在此地点）
        for other in ctx.game_state.investigators.values():
            if other.location_id != inv.location_id:
                continue
            for enemy_iid in list(other.threat_area):
                enemy = ctx.game_state.get_card_instance(enemy_iid)
                if enemy is None:
                    continue
                other.threat_area.remove(enemy_iid)
                enemy.exhausted = True
                if enemy_iid not in loc.enemies:
                    loc.enemies.append(enemy_iid)
                evaded.append(enemy_iid)
        # 未交战敌人横置（自动躲避）
        for enemy_iid in list(loc.enemies):
            enemy = ctx.game_state.get_card_instance(enemy_iid)
            if enemy is None or enemy.exhausted:
                continue
            enemy.exhausted = True
            evaded.append(enemy_iid)

        ctx.extra["cunning_distraction_evaded"] = evaded
        if evaded:
            ctx.game_state.log_effect(
                f"🌀 调虎离山：自动躲避了{len(evaded)}个敌人")
