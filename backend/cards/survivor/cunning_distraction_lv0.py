"""Cunning Distraction (Level 0) — Survivor Event.
所有与你交战的敌人失去交战，移动到一个你选择的已揭示地点。

简化说明：
- 目标地点默认为第一个连接地点，可用 ctx.extra["destination"] 指定。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class CunningDistraction(CardImplementation):
    card_id = "cunning_distraction_lv0"

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def disengage_all(self, ctx):
        if ctx.extra.get("card_id") != "cunning_distraction_lv0":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        cur_loc = ctx.game_state.get_location(inv.location_id)
        if cur_loc is None:
            return

        destination = ctx.extra.get("destination")
        if destination is None:
            connections = getattr(cur_loc, "connections", []) or []
            destination = connections[0] if connections else None
        if destination is None or destination not in ctx.game_state.locations:
            return

        target_loc = ctx.game_state.get_location(destination)
        moved = []
        for enemy_iid in list(inv.threat_area):
            inv.threat_area.remove(enemy_iid)
            enemy = ctx.game_state.get_card_instance(enemy_iid)
            if enemy is not None:
                enemy.exhausted = True
                target_loc.enemies.append(enemy_iid)
                enemy.attached_to = destination
                moved.append(enemy_iid)
        ctx.extra["cunning_distraction_moved"] = moved
