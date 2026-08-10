"""Caught Red-Handed (Level 0) — Neutral Treachery, Weakness.
显现：准备你所在地点或连接地点的每个敌人。每个在连接地点的猎手敌人
向你移动1个地点。若没有敌人因此效果移动，将当场抓获洗回你的牌组。

简化说明：
- "猎手向你移动1个地点"近似为：连接地点的猎手敌人直接移动到你的地点
  （引擎无地点图路径搜索——引擎缺口；单连接步距下等价）。
- 移动的是未交战敌人（在地点的 enemies 列表）；已交战敌人跟随调查员，
  不在本效果范围。
"""

import random

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class CaughtRedHanded(CardImplementation):
    card_id = "caught_red_handed_lv0"

    @on_event(GameEvent.CARD_DRAWN, priority=TimingPriority.WHEN)
    def revelation(self, ctx):
        if ctx.extra.get("card_id") != "caught_red_handed_lv0":
            return
        game_state = ctx.game_state
        inv = game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if "caught_red_handed_lv0" in inv.hand:
            inv.hand.remove("caught_red_handed_lv0")

        here = game_state.get_location(inv.location_id)
        area_ids = [inv.location_id] + list(here.connections if here else [])

        # 准备你所在地点或连接地点的每个敌人
        readied = 0
        for loc_id in area_ids:
            loc = game_state.get_location(loc_id)
            if loc is None:
                continue
            for enemy_id in loc.enemies:
                enemy = game_state.get_card_instance(enemy_id)
                if enemy is not None and enemy.exhausted:
                    enemy.exhausted = False
                    readied += 1

        # 连接地点的猎手敌人移动到你的地点
        moved = 0
        if here is not None:
            for loc_id in list(here.connections):
                loc = game_state.get_location(loc_id)
                if loc is None:
                    continue
                for enemy_id in list(loc.enemies):
                    enemy = game_state.get_card_instance(enemy_id)
                    enemy_data = (
                        game_state.get_card_data(enemy.card_id) if enemy else None
                    )
                    if enemy_data is None:
                        continue
                    if "hunter" not in (enemy_data.keywords or []):
                        continue
                    loc.enemies.remove(enemy_id)
                    here.enemies.append(enemy_id)
                    moved += 1

        ctx.extra["caught_red_handed"] = {"readied": readied, "moved": moved}
        if moved == 0:
            inv.deck.append("caught_red_handed_lv0")
            random.shuffle(inv.deck)
            ctx.extra["caught_red_handed"]["shuffled_back"] = True
            game_state.log_effect("🚨 当场抓获：无敌人移动，洗回牌组")
        else:
            inv.discard.append("caught_red_handed_lv0")
            game_state.log_effect(f"🚨 当场抓获：{moved}个猎手逼近")
