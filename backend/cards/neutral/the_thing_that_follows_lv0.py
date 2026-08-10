"""The Thing That Follows (Level 0) — Neutral Enemy, Basic Weakness.
生成 - 离你最远的地点。猎物 - 仅对承受者。猎手。
强制 - 随行鬼影将要被击败时：改为将其洗入承受者的牌组。

简化说明：
- "将要被击败时改为洗入牌组"挂在 ENEMY_DEFEATED：handler 在引擎移除敌人
  之前把实例移出场上并洗入承受者牌组，引擎随后的移除找不到实例即中止
  （damage._defeat_enemy/_remove_enemy_from_play 对缺失实例直接返回）。
- 生成位置（最远地点）与猎物（仅承受者）依赖引擎生成/交战通道，未接线，
  由会话层负责；敌人数据（战斗3/生命2/躲避3/伤害1/恐惧1，猎手）不在玩家卡
  JSON 加载通道内（同 graveyard_ghouls_lv0 的说明）。
"""

import random

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class TheThingThatFollows(CardImplementation):
    card_id = "the_thing_that_follows_lv0"

    @on_event(GameEvent.ENEMY_DEFEATED, priority=TimingPriority.WHEN)
    def shuffle_into_deck_instead(self, ctx):
        if ctx.extra.get("card_id") != "the_thing_that_follows_lv0":
            return
        enemy = ctx.game_state.get_card_instance(ctx.target)
        if enemy is None:
            return
        bearer_id = enemy.owner_id

        # 在引擎移除之前先移出场上（威胁区/地点/在场表）
        for inv in ctx.game_state.investigators.values():
            if ctx.target in inv.threat_area:
                inv.threat_area.remove(ctx.target)
        for loc in ctx.game_state.locations.values():
            if ctx.target in loc.enemies:
                loc.enemies.remove(ctx.target)
        ctx.game_state.cards_in_play.pop(ctx.target, None)

        # 洗入承受者牌组
        bearer = ctx.game_state.get_investigator(bearer_id)
        if bearer is not None:
            bearer.deck.append("the_thing_that_follows_lv0")
            random.shuffle(bearer.deck)
            ctx.game_state.log_effect("👤 随行鬼影：未被击败，洗入承受者牌组")

        ctx.extra["thing_that_follows_shuffled"] = bearer_id
