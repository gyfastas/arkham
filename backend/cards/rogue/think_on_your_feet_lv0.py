"""Think on Your Feet (Level 0) — Rogue Event.
快速。在敌人将要在你所在地点生成时打出。
立刻移动到一个连接地点。(该敌人依然在原本地点生成。)

简化说明：
- 移动目标简化为第一个连接地点（目标选择由会话层 UI 提供后可扩展）。
- 打出时机由会话层校验。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class ThinkOnYourFeet(CardImplementation):
    card_id = "think_on_your_feet_lv0"

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def move_to_connected(self, ctx):
        if ctx.extra.get("card_id") != "think_on_your_feet_lv0":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
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
        ctx.extra["think_on_your_feet_moved_to"] = destination
