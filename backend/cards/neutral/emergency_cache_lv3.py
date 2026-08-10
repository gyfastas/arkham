"""Emergency Cache (Level 3) — Neutral Event.
获得4资源，或将4个补给标记分配给你所在地点的调查员控制的支援卡，
或以任意形式组合（总数为4）。

简化说明：
- 打出时默认走"获得4资源"分支（最常用）；补给/组合分支由会话层改调
  resolve_supplies()（打出后不要再调用，否则会重复结算）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class EmergencyCacheLv3(CardImplementation):
    card_id = "emergency_cache_lv3"

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.AFTER)
    def gain_resources(self, ctx):
        """默认分支：获得4资源。"""
        if ctx.extra.get("card_id") != "emergency_cache_lv3":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv:
            inv.resources += 4
            ctx.extra["emergency_cache_lv3"] = {"resources": 4, "supplies": {}}

    def resolve_supplies(self, game_state, investigator_id,
                         resources: int = 0, supplies: dict | None = None) -> bool:
        """组合分支：resources 点资源 + supplies {instance_id: 补给数}，总数须为4。

        补给只能放到你所在地点的调查员控制的支援卡上。
        """
        supplies = dict(supplies or {})
        if resources < 0 or any(n <= 0 for n in supplies.values()):
            return False
        if resources + sum(supplies.values()) != 4:
            return False
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return False

        local_ids = {
            other.investigator_id
            for other in game_state.get_investigators_at_location(inv.location_id)
        }
        for iid, n in supplies.items():
            inst = game_state.get_card_instance(iid)
            if inst is None or inst.controller_id not in local_ids:
                return False
        inv.resources += resources
        for iid, n in supplies.items():
            inst = game_state.get_card_instance(iid)
            inst.uses["supply"] = inst.uses.get("supply", 0) + n
        return True
