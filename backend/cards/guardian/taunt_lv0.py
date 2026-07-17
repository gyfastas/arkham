"""Taunt (Level 0) — Guardian Event.
快速。只能在你回合中打出。与你所在地点的任意数量敌人交战。

简化说明：
- "快速/只能在你回合中打出"的时机由会话层校验。
- 交战不发出 ENEMY_ENGAGED 事件（handler 无法访问事件总线），
  因此佐伊等"交战时"反应不会因本卡触发，特此注明。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class Taunt(CardImplementation):
    card_id = "taunt_lv0"

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def engage_enemies(self, ctx):
        """与你所在地点的所有敌人交战。"""
        if ctx.extra.get("card_id") != "taunt_lv0":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        location = ctx.game_state.get_location(inv.location_id)
        if location is None:
            return

        engaged = engage_all_at_location(ctx.game_state, inv, location)
        ctx.extra["taunt_engaged"] = engaged


def engage_all_at_location(game_state, inv, location) -> list[str]:
    """把地点所有未交战敌人移到调查员威胁区域（交战）。"""
    engaged = []
    for enemy_id in list(location.enemies):
        enemy = game_state.get_card_instance(enemy_id)
        if enemy is None:
            continue
        location.enemies.remove(enemy_id)
        if enemy_id not in inv.threat_area:
            inv.threat_area.append(enemy_id)
        engaged.append(enemy_id)
    return engaged
