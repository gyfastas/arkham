"""Hallowed Mirror (Level 0) — Guardian Asset, Accessory slot. (05313)
每卡组限1张。
强制 - 圣化之镜入场后：在你的绑定卡牌中查找3张舒缓旋律。将其中1张加入
手牌，其余2张洗入牌库。当圣化之镜离场时，找到这些舒缓旋律的每一张
（即使它们在游戏外），将它们移出游戏。

简化说明：
- 绑定卡（soothing_melody_lv0）需在卡数据中已注册，否则效果跳过
  （绑定卡不在牌库中，由绑定机制提供；同 miss_doyle 的约定）。
- 离场扫尾：手牌/牌库/弃牌堆中的舒缓旋律全部移出游戏
  （scenario.vars["out_of_play"]）；已结算入弃牌堆的也算。
"""

import random

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority

_BONDED = "soothing_melody_lv0"


class HallowedMirror(CardImplementation):
    card_id = "hallowed_mirror_lv0"

    @on_event(GameEvent.CARD_ENTERS_PLAY, priority=TimingPriority.FORCED)
    def fetch_bonded(self, ctx):
        """入场后：1张舒缓旋律入手，其余2张洗入牌库。"""
        if ctx.target != self.instance_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if ctx.game_state.get_card_data(_BONDED) is None:
            return
        inv.hand.append(_BONDED)
        inv.deck.extend([_BONDED, _BONDED])
        random.shuffle(inv.deck)
        ctx.extra["hallowed_mirror_bonded"] = True
        ctx.game_state.log_effect(
            "🪞 圣化之镜：1张【舒缓旋律】加入手牌，其余2张洗入牌库")

    @on_event(GameEvent.CARD_LEAVES_PLAY, priority=TimingPriority.AFTER)
    def set_aside_on_leave(self, ctx):
        """离场时：所有舒缓旋律（无论何在）移出游戏。"""
        if ctx.target != self.instance_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            inst = ctx.game_state.get_card_instance(self.instance_id)
            inv = ctx.game_state.get_investigator(
                getattr(inst, "owner_id", "") or "")
        if inv is None:
            return
        out = ctx.game_state.scenario.vars.setdefault("out_of_play", [])
        for zone in (inv.hand, inv.deck, inv.discard):
            while _BONDED in zone:
                zone.remove(_BONDED)
                out.append(_BONDED)
        ctx.game_state.log_effect("🪞 圣化之镜离场：舒缓旋律移出游戏")
