"""Elusive (Level 0) — Rogue Event.
快速。仅在你的回合中打出。
与每个与你交战的敌人脱离交战，移动到一个没有敌人的已揭示地点。

简化说明：
- 目标地点自动选择：优先第一个没有敌人的已揭示连接地点，
  否则回退到任意没有敌人的已揭示地点（官方为玩家自选任意
  符合条件的地点）；可用 ctx.extra["destination"] 指定。
- "仅在你的回合中打出"的时机校验由会话层负责。
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

        # 目标地点：无敌人的已揭示地点（优先连接地点，回退任意地点）
        destination = ctx.extra.get("destination")
        if destination is None and cur_loc is not None:
            for conn_id in cur_loc.connections or []:
                conn = ctx.game_state.get_location(conn_id)
                if conn is not None and conn.revealed and not conn.enemies:
                    destination = conn_id
                    break
        if destination is None:
            for loc_id, loc in ctx.game_state.locations.items():
                if loc_id == inv.location_id:
                    continue
                if loc.revealed and not loc.enemies:
                    destination = loc_id
                    break
        if destination is None or destination not in ctx.game_state.locations:
            return
        inv.location_id = destination
        ctx.extra["elusive_moved_to"] = destination
