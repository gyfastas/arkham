"""Shortcut (Level 0) — Seeker Event, Fast.
快速。只能在你回合中打出。选择你所在地点的一位调查员。将该调查员移动到一个连接地点。

简化说明：
- "快速/只能在你回合中打出"的时机由会话层校验。
- 单人模式默认移动自己；目标地点可通过 ctx.extra["destination"] 指定，
  否则取第一个连接地点。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class Shortcut(CardImplementation):
    card_id = "shortcut_lv0"

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def move_investigator(self, ctx):
        """将你所在地点的一名调查员移动到连接地点。"""
        if ctx.extra.get("card_id") != "shortcut_lv0":
            return
        # 目标调查员：默认打出者，可用 ctx.extra["target_investigator"] 指定
        target_id = ctx.extra.get("target_investigator") or ctx.investigator_id
        inv = ctx.game_state.get_investigator(target_id)
        if inv is None:
            return
        location = ctx.game_state.get_location(inv.location_id)
        if location is None:
            return
        connections = getattr(location, "connections", []) or []
        destination = ctx.extra.get("destination") or (connections[0] if connections else None)
        if destination is None or destination not in ctx.game_state.locations:
            return
        inv.location_id = destination
        ctx.extra["shortcut_moved_to"] = destination
