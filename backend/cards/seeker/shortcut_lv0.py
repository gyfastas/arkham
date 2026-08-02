"""Shortcut (Level 0) — Seeker Event, Fast.
快速。只能在你回合中打出。选择你所在地点的一位调查员。将该调查员移动到一个连接地点。

实现说明：
- 打出后不立即移动，而是写入 scenario.vars["pending_choice"]
  (kind="shortcut_move")；前端 ChoiceModal 弹出连接地点列表，
  玩家选择后由 session 层 _resolve_choice 校验并完成移动。
- 单人模式目标调查员默认为打出者；多人可用 ctx.extra["target_investigator"]。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class Shortcut(CardImplementation):
    card_id = "shortcut_lv0"

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def move_investigator(self, ctx):
        """将你所在地点的一名调查员移动到连接地点（由玩家选择目的地）。"""
        if ctx.extra.get("card_id") != "shortcut_lv0":
            return
        target_id = ctx.extra.get("target_investigator") or ctx.investigator_id
        inv = ctx.game_state.get_investigator(target_id)
        if inv is None:
            return
        location = ctx.game_state.get_location(inv.location_id)
        if location is None:
            return
        connections = list(getattr(location, "connections", []) or [])
        if not connections:
            return

        def _label(loc_id: str) -> str:
            loc = ctx.game_state.get_location(loc_id)
            if loc is not None and loc.card_data is not None:
                return loc.card_data.name_cn or loc.card_data.name
            return loc_id

        ctx.game_state.scenario.vars["pending_choice"] = {
            "kind": "shortcut_move",
            "investigator_id": target_id,
            "from_location": inv.location_id,
            "prompt": "<b>捷径</b>：选择一个连接地点，将该调查员移动过去",
            "options": [
                {"id": loc_id, "label": _label(loc_id)} for loc_id in connections
            ],
        }
        ctx.extra["shortcut_pending"] = True
