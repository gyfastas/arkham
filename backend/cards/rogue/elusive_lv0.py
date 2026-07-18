"""Elusive (Level 0) — Rogue Event.
快速。与所有敌人脱离交战，移动到一个没有敌人的已揭示地点。

简化说明：
- 目标地点默认为第一个没有敌人的已揭示连接地点，
  可用 ctx.extra["destination"] 指定。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class Elusive(CardImplementation):
    card_id = "elusive_lv0"

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def disengage_and_move(self, ctx):
        if ctx.extra.get("card_id") != "elusive_lv0":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return

        # 与所有敌人脱离交战：放回当前地点
        cur_loc = ctx.game_state.get_location(inv.location_id)
        for enemy_iid in list(inv.threat_area):
            inv.threat_area.remove(enemy_iid)
            if cur_loc is not None and enemy_iid not in cur_loc.enemies:
                cur_loc.enemies.append(enemy_iid)

        # 目标地点：无敌人的已揭示地点
        destination = ctx.extra.get("destination")
        if destination is None and cur_loc is not None:
            for conn_id in getattr(cur_loc, "connections", []) or []:
                conn = ctx.game_state.get_location(conn_id)
                if conn is not None and not conn.enemies:
                    destination = conn_id
                    break
        if destination is None or destination not in ctx.game_state.locations:
            return
        inv.location_id = destination
        ctx.extra["elusive_moved_to"] = destination
