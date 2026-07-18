"""Barricade (Level 0) — Seeker Event.
将屏障附加到你所在地点。被附加的地点不能生成非精英敌人。

简化说明：
- 附加关系记录在 scenario.vars["barricaded_locations"]；
  敌人生成逻辑（official_core._spawn_enemy_from_encounter）已接入检查。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class Barricade(CardImplementation):
    card_id = "barricade_lv0"

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def attach_to_location(self, ctx):
        if ctx.extra.get("card_id") != "barricade_lv0":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        locations = ctx.game_state.scenario.vars.setdefault("barricaded_locations", [])
        if inv.location_id not in locations:
            locations.append(inv.location_id)
        ctx.extra["barricaded_location"] = inv.location_id
