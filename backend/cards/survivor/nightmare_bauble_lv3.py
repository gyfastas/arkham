"""Nightmare Bauble (Level 3) — Survivor Asset, Accessory slot. (08054 批次)
Limit 1 per deck.
Forced - After Nightmare Bauble enters play: Search your bonded cards for
3 copies of Dream Parasite and attach them to Nightmare Bauble. When
Nightmare Bauble leaves play, set each attached Dream Parasite aside, out
of play.
[reaction] When you reveal an [auto_fail] chaos token, shuffle an attached
Dream Parasite into your deck: Cancel that token.

简化说明：
- 羁绊的梦寄生虫（dream_parasite_lv0）以计数跟踪（不入 cards_in_play；
  其"在手牌中必须投入"等自身效果需会话层支持，见报告）。
- "洗入牌库"简化为置于牌堆顶附近随机插入（random.shuffle 整库）。
- 取消自动失败经 CHAOS_TOKEN_RESOLVED 的 ctx.extra["cancel_auto_fail"]
  通道（引擎在 ST.4 结算后清除 auto_fail）。
"""

import random

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import ChaosTokenType, GameEvent, TimingPriority

_PARASITE_ID = "dream_parasite_lv0"
_PARASITE_COPIES = 3


class NightmareBauble(CardImplementation):
    card_id = "nightmare_bauble_lv3"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._parasites = 0  # 已附加的梦寄生虫数量

    @on_event(GameEvent.CARD_ENTERS_PLAY, priority=TimingPriority.AFTER)
    def attach_parasites(self, ctx):
        """入场后：搜寻3张羁绊的梦寄生虫并附加。"""
        if ctx.target != self.instance_id:
            return
        self._parasites = _PARASITE_COPIES
        ctx.game_state.log_effect(
            f"📿 梦魇挂饰：附加{_PARASITE_COPIES}张梦寄生虫")

    @on_event(GameEvent.CARD_LEAVES_PLAY, priority=TimingPriority.AFTER)
    def set_aside_on_leave(self, ctx):
        """离场时：将附加的梦寄生虫移出游戏。"""
        if ctx.target != self.instance_id or self._parasites <= 0:
            return
        out = ctx.game_state.scenario.vars.setdefault("out_of_play", [])
        out.extend([_PARASITE_ID] * self._parasites)
        self._parasites = 0

    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.WHEN)
    def cancel_auto_fail(self, ctx):
        """你揭示自动失败标记时：洗一张梦寄生虫回牌库，取消该标记。"""
        if ctx.chaos_token != ChaosTokenType.AUTO_FAIL or self._parasites <= 0:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        self._parasites -= 1
        inv.deck.append(_PARASITE_ID)
        random.shuffle(inv.deck)
        ctx.extra["cancel_auto_fail"] = True
        ctx.extra["nightmare_bauble_cancelled"] = True
        ctx.game_state.log_effect(
            "📿 梦魇挂饰：洗一张梦寄生虫回牌库，取消自动失败标记")
