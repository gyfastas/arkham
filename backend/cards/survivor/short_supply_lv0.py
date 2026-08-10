"""Short Supply (Level 0) — Survivor Asset (Permanent). (08071)
永久。每副牌组限制1张。当牌组构建时购买。
强制 - 在你游戏的第一回合开始时：丢弃你牌堆顶部10张卡牌。

简化说明：
- "永久"（开局即在场、购买时机）由会话/构筑层处理；本实现假定已在场。
- 强制效果挂 INVESTIGATOR_TURN_BEGINS：所有者本局第一个回合开始时丢弃
  牌堆顶10张（不足10张则全丢），以实现实例标记保证只触发一次。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class ShortSupply(CardImplementation):
    card_id = "short_supply_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._done = False

    @on_event(GameEvent.INVESTIGATOR_TURN_BEGINS, priority=TimingPriority.FORCED)
    def discard_top_ten(self, ctx):
        """强制 - 你的第一个回合开始时：丢弃牌堆顶10张。"""
        if self._done:
            return
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is None or inst.owner_id != ctx.investigator_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        self._done = True
        discarded = 0
        for _ in range(10):
            if not inv.deck:
                break
            inv.discard.append(inv.deck.pop(0))
            discarded += 1
        ctx.extra["short_supply_discarded"] = discarded
        ctx.game_state.log_effect(f"📉 补给匮乏：丢弃牌堆顶{discarded}张卡牌")
