"""Deep Knowledge (Level 0) — Seeker Event. (07023)
作为打出深奥知识的额外费用，向混沌袋中添加2个[诅咒]标记。
你所在地点的调查员们合计抽取3张牌（由你决定每名调查员各抽几张）。

简化说明：
- 混沌袋经 bind_chaos_bag 注入（registry.activate_card 生产环境自动接线；
  未绑定时仅跳过加标记，抽牌效果照常——测试可手动绑定）；
- 分配方案缺省为你自己抽3张（官方为你自由分配）；可经 CARD_PLAYED 的
  ctx.extra["distribution"] = {investigator_id: 张数} 指定（合计3张）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import ChaosTokenType, GameEvent, TimingPriority

CURSE_TOKENS = 2
TOTAL_DRAWS = 3


class DeepKnowledge(CardImplementation):
    card_id = "deep_knowledge_lv0"

    def bind_chaos_bag(self, chaos_bag) -> None:
        self._bag = chaos_bag

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def resolve(self, ctx):
        if ctx.extra.get("card_id") != self.card_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return

        # 额外费用：向混沌袋添加2个[诅咒]
        bag = getattr(self, "_bag", None)
        if bag is not None:
            for _ in range(CURSE_TOKENS):
                bag.add_token(ChaosTokenType.CURSE)

        # 同地点调查员合计抽3张（缺省全部分配给你）
        distribution = ctx.extra.get("distribution")
        if not distribution:
            distribution = {inv.investigator_id: TOTAL_DRAWS}
        location_id = inv.location_id
        drawn_total = 0
        for inv_id, count in distribution.items():
            target = ctx.game_state.get_investigator(inv_id)
            if target is None or target.location_id != location_id:
                continue
            for _ in range(min(count, TOTAL_DRAWS - drawn_total)):
                if drawn_total >= TOTAL_DRAWS or not target.deck:
                    break
                target.hand.append(target.deck.pop(0))
                drawn_total += 1

        ctx.extra["deep_knowledge_drawn"] = drawn_total
        ctx.game_state.log_effect(
            f"📚 深奥知识：袋中添加2个[诅咒]，同地点调查员合计抽{drawn_total}张牌"
        )
