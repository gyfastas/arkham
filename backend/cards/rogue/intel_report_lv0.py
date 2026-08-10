"""Intel Report (Level 0) — Rogue Event. (05111)
在你所在地点发现1个线索。
[反应]当你打出情报报告时，将其费用提高2：将"发现1个线索"改为"发现2个线索"。
[反应]当你打出情报报告时，将其费用提高2：将"在你所在地点"改为"在至多
2步连接外的一个地点"。

简化说明：
- 两项升级为打出时的可选追加费用；引擎打出流程不支持附加选项
  （actions._play_event 无选项通道，引擎缺口），改为读取 CARD_PLAYED
  上下文的 extra 注入（"intel_report_two_clues" / 
  "intel_report_remote_location"），每项追加费2资源（资源不足则忽略
  该升级）。测试/会话层可在发射事件时注入。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority

_UPGRADE_COST = 2
_MAX_DISTANCE = 2


class IntelReport(CardImplementation):
    card_id = "intel_report_lv0"

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def resolve(self, ctx):
        if ctx.extra.get("card_id") != "intel_report_lv0":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return

        two_clues = bool(ctx.extra.get("intel_report_two_clues"))
        remote_location = ctx.extra.get("intel_report_remote_location")
        if two_clues and inv.resources >= _UPGRADE_COST:
            inv.resources -= _UPGRADE_COST
            ctx.extra["intel_report_upgraded_clues"] = True
        else:
            two_clues = False
        if remote_location and inv.resources >= _UPGRADE_COST and \
                self._within_distance(ctx.game_state, inv.location_id,
                                      remote_location, _MAX_DISTANCE):
            inv.resources -= _UPGRADE_COST
            ctx.extra["intel_report_upgraded_range"] = True
        else:
            remote_location = None

        location_id = remote_location or inv.location_id
        loc = ctx.game_state.get_location(location_id)
        if loc is None:
            return
        amount = 2 if two_clues else 1
        discovered = min(amount, loc.clues)
        if discovered <= 0:
            return
        loc.clues -= discovered
        inv.clues += discovered
        ctx.extra["intel_report_discovered"] = discovered
        ctx.game_state.log_effect(
            f"📄 情报报告：在【{ctx.game_state.card_name(location_id)}】"
            f"发现{discovered}个线索")

    @staticmethod
    def _within_distance(game_state, start_id: str, target_id: str,
                         max_distance: int) -> bool:
        """BFS 判定 target 是否在 start 的 max_distance 步连接内。"""
        if target_id == start_id:
            return True
        frontier = [start_id]
        seen = {start_id}
        for _ in range(max_distance):
            nxt = []
            for loc_id in frontier:
                loc = game_state.get_location(loc_id)
                if loc is None:
                    continue
                for conn in loc.connections:
                    if conn == target_id:
                        return True
                    if conn not in seen:
                        seen.add(conn)
                        nxt.append(conn)
            frontier = nxt
        return False
