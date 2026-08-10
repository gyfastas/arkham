"""Stargazing (Level 1) — Mystic Event. (06027)
每场游戏最多两次。遭遇牌堆有10张以上卡牌时才能打出。
在你的绑定卡牌中查找1张群星正确之时，并将其混洗入遭遇牌堆顶部10张卡牌中。

简化/缺口说明：
- 引擎无"绑定卡牌"区：直接从游戏外取 the_stars_are_right_lv0 加入遭遇牌堆
  （绑定卡的数据 id 固定）。
- "混洗入顶部10张"：插入到前10张内的随机位置（随机数取自注入的混沌袋
  _rng，未绑定时回退 random 模块）。
- 打出限制（遭遇牌堆≥10张、每场最多两次）无法在打出前拦截（引擎无打出前
  事件），改为打出后校验：不满足则效果不生效并记录日志；次数登记在
  scenario.vars["stargazing_played"]。
"""

import random

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority

_STARS_CARD_ID = "the_stars_are_right_lv0"


class Stargazing(CardImplementation):
    card_id = "stargazing_lv1"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._bag = None

    def bind_chaos_bag(self, chaos_bag) -> None:
        self._bag = chaos_bag

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def shuffle_stars_into_encounter_deck(self, ctx):
        if ctx.extra.get("card_id") != self.card_id:
            return
        scen = ctx.game_state.scenario
        played = scen.vars.get("stargazing_played", 0)
        if played >= 2:
            ctx.game_state.log_effect("🌠 仰望星空：每场游戏最多两次，效果不生效")
            return
        deck = scen.encounter_deck
        if len(deck) < 10:
            ctx.game_state.log_effect(
                "🌠 仰望星空：遭遇牌堆不足10张，效果不生效")
            return
        rng = self._bag._rng if self._bag is not None else random
        idx = rng.randint(0, 9)
        deck.insert(idx, _STARS_CARD_ID)
        scen.vars["stargazing_played"] = played + 1
        ctx.extra["stargazing_inserted"] = idx
        ctx.game_state.log_effect(
            "🌠 仰望星空：将【群星正确之时】混洗入遭遇牌堆顶部10张")
