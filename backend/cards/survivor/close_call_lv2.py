"""Close Call (Level 2) — Survivor Event.
快速。在你躲避一个敌人后打出。将该敌人洗入遭遇牌堆。

简化说明：
- 从手牌中自动触发：你成功躲避敌人后自动打出。
"""

import random

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class CloseCall(CardImplementation):
    card_id = "close_call_lv2"

    @on_event(GameEvent.ENEMY_EVADED, priority=TimingPriority.AFTER)
    def shuffle_enemy_away(self, ctx):
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or "close_call_lv2" not in inv.hand:
            return
        enemy_iid = ctx.enemy_id or ctx.extra.get("enemy_id")
        enemy = ctx.game_state.get_card_instance(enemy_iid) if enemy_iid else None
        if enemy is None:
            return

        # 自动打出
        cd = ctx.game_state.get_card_data("close_call_lv2")
        cost = getattr(cd, "cost", 2) or 2 if cd else 2
        if inv.resources < cost:
            return
        inv.resources -= cost
        inv.hand.remove("close_call_lv2")
        inv.discard.append("close_call_lv2")

        # 将敌人洗入遭遇牌堆
        scenario = ctx.game_state.scenario
        for loc in ctx.game_state.locations.values():
            if enemy_iid in loc.enemies:
                loc.enemies.remove(enemy_iid)
        ctx.game_state.cards_in_play.pop(enemy_iid, None)
        scenario.encounter_deck.append(enemy.card_id)
        random.shuffle(scenario.encounter_deck)
        ctx.extra["close_call_shuffled"] = enemy.card_id
