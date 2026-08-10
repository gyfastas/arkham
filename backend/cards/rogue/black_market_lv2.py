"""Black Market (Level 2) — Rogue Event. (08055)
快速。当调查阶段开始时打出。
依次从任一调查员的牌堆顶部揭示卡牌，直到正好揭示5张卡牌。将这些卡牌放在
一边，位于场外。只要这些卡牌放在一边，任何调查员可以将其视为自己的手牌
打出。当下次调查阶段开始时，将仍放在一边的这些卡牌混洗入其所有者的牌堆。

简化说明：
- 揭示来源简化为仅打出者自己的牌堆顶5张（官方可混合任意调查员牌堆；
  多人混抽需要目标选择 UI）。
- "视为手牌打出"需要会话层支持：预留牌公开在
  scenario.vars["black_market_set_aside"]（含 owner 与 cards），会话层
  据此放行打出；卡牌代码无法扩展打出合法性校验（引擎缺口，见报告）。
- 事件实现实例在 ROUND_ENDS 会被引擎清理，而归还发生在下个调查阶段开始；
  本实现在 ROUND_ENDS（REACTION，清理之后）自我续注册，归还后注销。
"""

import random

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority

_VARS_KEY = "black_market_set_aside"


class BlackMarket(CardImplementation):
    card_id = "black_market_lv2"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._bus = None
        self._owner_id: str | None = None
        self._set_aside: list[str] = []

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def reveal_five(self, ctx):
        """打出：揭示你牌堆顶5张，放于一旁（场外）。"""
        if ctx.extra.get("card_id") != self.card_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        self._owner_id = inv.investigator_id
        count = min(5, len(inv.deck))
        self._set_aside = list(inv.deck[:count])
        del inv.deck[:count]
        ctx.game_state.scenario.vars[_VARS_KEY] = {
            "owner": self._owner_id,
            "cards": list(self._set_aside),
        }
        ctx.extra["black_market_set_aside"] = list(self._set_aside)
        names = "、".join(ctx.game_state.card_name(c) for c in self._set_aside)
        ctx.game_state.log_effect(f"🕶️ 黑市：揭示并置于一旁——{names}")

    @on_event(GameEvent.ROUND_ENDS, priority=TimingPriority.REACTION)
    def survive_round_cleanup(self, ctx):
        """预留牌未归还时，在引擎清理事件实例后自我续注册到总线。"""
        if not self._set_aside or self._bus is None:
            return
        self.register(self._bus, self.instance_id)

    @on_event(GameEvent.INVESTIGATION_PHASE_BEGINS, priority=TimingPriority.AFTER)
    def shuffle_back(self, ctx):
        """下个调查阶段开始：仍预留的牌洗回其所有者牌堆，并注销自身。"""
        if not self._set_aside:
            return
        inv = ctx.game_state.get_investigator(self._owner_id)
        if inv is not None:
            inv.deck.extend(self._set_aside)
            random.shuffle(inv.deck)
        returned = list(self._set_aside)
        self._set_aside = []
        ctx.game_state.scenario.vars.pop(_VARS_KEY, None)
        ctx.extra["black_market_returned"] = returned
        ctx.game_state.log_effect(
            f"🕶️ 黑市：{len(returned)}张预留牌洗回所有者牌堆")
        if self._bus is not None:
            self._bus.unregister_card(self.instance_id)
