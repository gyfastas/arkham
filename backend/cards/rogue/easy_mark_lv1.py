"""Easy Mark (Level 1) — Rogue Event. (06026)
多重。
获得2资源并抽取1张卡牌。
[反应]在你打出冤大头后：从你手牌中免费打出另一张冤大头。

简化说明：
- 连锁自动触发（官方为玩家选择）：打出后若手牌还有另一张冤大头，自动
  免费打出（移除手牌、入弃牌堆并再次发出 CARD_PLAYED）。
- 连锁深度限制为2（牌组同名至多3张——"多重"），防止异常递归。
- "多重"（牌组限3张）为牌组构建规则，由会话层负责。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority

_MAX_CHAIN_DEPTH = 2  # 原始打出为0，连锁至多再打出2张


class EasyMark(CardImplementation):
    card_id = "easy_mark_lv1"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._bus = None

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.AFTER)
    def gain_and_chain(self, ctx):
        """获得2资源并抽1张牌；然后连锁免费打出另一张冤大头。"""
        if ctx.extra.get("card_id") != self.card_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        inv.resources += 2
        if inv.deck:
            inv.hand.append(inv.deck.pop(0))
        ctx.game_state.log_effect("💰 冤大头：获得2资源并抽1张牌")

        depth = int(ctx.extra.get("easy_mark_chain_depth", 0) or 0)
        if depth >= _MAX_CHAIN_DEPTH or self._bus is None:
            return
        if self.card_id not in inv.hand:
            return
        # 连锁：从手牌免费打出另一张冤大头
        inv.hand.remove(self.card_id)
        inv.discard.append(self.card_id)
        ctx.game_state.log_effect("💰 冤大头：连锁免费打出另一张冤大头")
        from backend.engine.event_bus import EventContext
        self._bus.emit(EventContext(
            game_state=ctx.game_state,
            event=GameEvent.CARD_PLAYED,
            investigator_id=ctx.investigator_id,
            source=ctx.source,
            extra={
                "card_id": self.card_id,
                "easy_mark_chain_depth": depth + 1,
            },
        ))
