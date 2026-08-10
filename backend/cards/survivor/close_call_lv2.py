"""Close Call (Level 2) — Survivor Event.
Fast. Play after a non-weakness, non-Elite enemy at your location is evaded.
Shuffle that enemy into the encounter deck.

简化说明：
- 从手牌中自动触发：满足条件（你所在地点的非弱点非精英敌人被躲避，
  允许其他调查员躲避触发）且资源足够时自动打出（官方为玩家选择时机）。
"""

import random

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority
from backend.models.state import is_weakness_card
from backend.scenarios.official_core import is_elite_enemy


class CloseCall(CardImplementation):
    card_id = "close_call_lv2"

    @on_event(GameEvent.ENEMY_EVADED, priority=TimingPriority.AFTER)
    def shuffle_enemy_away(self, ctx):
        enemy_iid = ctx.enemy_id or ctx.extra.get("enemy_id")
        enemy = ctx.game_state.get_card_instance(enemy_iid) if enemy_iid else None
        if enemy is None:
            return
        enemy_data = ctx.game_state.get_card_data(enemy.card_id)
        if enemy_data is None:
            return
        # 非弱点、非精英
        if is_weakness_card(enemy_data) or "weakness" in (enemy_data.traits or []):
            return
        if is_elite_enemy(enemy_data):
            return

        # 被躲避的敌人在躲避者所在地点；找同地点手持千钧一发的调查员
        evader = ctx.game_state.get_investigator(ctx.investigator_id)
        if evader is None:
            return
        holder = None
        for cand in ctx.game_state.investigators.values():
            if cand.location_id != evader.location_id:
                continue
            if "close_call_lv2" in cand.hand:
                holder = cand
                break
        if holder is None:
            return

        # 自动打出
        cd = ctx.game_state.get_card_data("close_call_lv2")
        cost = getattr(cd, "cost", 2) or 2 if cd else 2
        if holder.resources < cost:
            return
        holder.resources -= cost
        holder.hand.remove("close_call_lv2")
        holder.discard.append("close_call_lv2")

        # 将敌人洗入遭遇牌堆
        scenario = ctx.game_state.scenario
        for loc in ctx.game_state.locations.values():
            if enemy_iid in loc.enemies:
                loc.enemies.remove(enemy_iid)
        ctx.game_state.cards_in_play.pop(enemy_iid, None)
        scenario.encounter_deck.append(enemy.card_id)
        random.shuffle(scenario.encounter_deck)
        ctx.extra["close_call_shuffled"] = enemy.card_id
        ctx.game_state.log_effect(
            f"🌀 千钧一发：【{ctx.game_state.card_name(enemy.card_id)}】洗入遭遇牌堆")
