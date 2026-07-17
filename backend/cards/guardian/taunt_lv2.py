"""Taunt (Level 2) — Guardian Event.
快速。只能在你回合中打出。与你所在地点的任意数量敌人交战。
你每通过该效果与一名敌人交战，抽取1张卡牌。

简化说明：
- "快速/只能在你回合中打出"的时机由会话层校验。
- 交战不发出 ENEMY_ENGAGED 事件（handler 无法访问事件总线）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.cards.guardian.taunt_lv0 import engage_all_at_location
from backend.models.enums import GameEvent, TimingPriority


class TauntLv2(CardImplementation):
    card_id = "taunt_lv2"

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def engage_and_draw(self, ctx):
        """与你所在地点的所有敌人交战，每交战1名抽1张牌。"""
        if ctx.extra.get("card_id") != "taunt_lv2":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        location = ctx.game_state.get_location(inv.location_id)
        if location is None:
            return

        engaged = engage_all_at_location(ctx.game_state, inv, location)
        ctx.extra["taunt_engaged"] = engaged

        for _ in engaged:
            if inv.deck:
                inv.hand.append(inv.deck.pop(0))
