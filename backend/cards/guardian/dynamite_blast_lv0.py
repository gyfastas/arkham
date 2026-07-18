"""Dynamite Blast (Level 0) — Guardian Event.
选择你所在地点或一个连接地点。对该地点的每个敌人和调查员造成3点伤害（包括你自己）。

简化说明：
- 目标地点默认为你所在地点，可用 ctx.extra["location"] 指定连接地点。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class DynamiteBlast(CardImplementation):
    card_id = "dynamite_blast_lv0"

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def blast(self, ctx):
        if ctx.extra.get("card_id") != "dynamite_blast_lv0":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        target_loc_id = ctx.extra.get("location") or inv.location_id
        location = ctx.game_state.get_location(target_loc_id)
        if location is None:
            return

        # 对该地点的每个敌人造成3点伤害
        for enemy_iid in list(location.enemies):
            enemy = ctx.game_state.get_card_instance(enemy_iid)
            if enemy is not None:
                enemy.damage += 3

        # 对该地点的每个调查员（包括自己）造成3点伤害
        for other in ctx.game_state.get_investigators_at_location(target_loc_id):
            other.damage += 3

        ctx.extra["dynamite_blast_location"] = target_loc_id
