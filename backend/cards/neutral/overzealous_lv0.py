"""Overzealous (Level 0) — Neutral Treachery, Basic Weakness.
显现：抽取遭遇牌堆顶的1张卡牌。该卡牌获得涌动。

简化说明：
- 遭遇卡的具体效果由遭遇/剧本层结算；本实现只把遭遇牌堆顶的卡移入
  遭遇弃牌堆（与 mythos 阶段抽遭遇卡后的去向一致），抽取记录写入
  ctx.extra["overzealous_drawn"] 供会话层继续结算。
- "涌动"简化为立即再抽一张遭遇卡（官方为先结算第一张的全部效果后再抽；
  单卡层面没有遭遇卡效果系统，故只多做一次抽牌）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class Overzealous(CardImplementation):
    card_id = "overzealous_lv0"

    @on_event(GameEvent.CARD_DRAWN, priority=TimingPriority.WHEN)
    def revelation(self, ctx):
        if ctx.extra.get("card_id") != "overzealous_lv0":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if "overzealous_lv0" in inv.hand:
            inv.hand.remove("overzealous_lv0")

        scenario = ctx.game_state.scenario
        drawn = []
        # 第一张遭遇卡 + 涌动补抽的一张
        for _ in range(2):
            if not scenario.encounter_deck:
                break
            card_id = scenario.encounter_deck.pop(0)
            scenario.encounter_discard.append(card_id)
            drawn.append(card_id)
            if len(drawn) == 1:
                ctx.game_state.log_effect("🔥 过度热心：抽取的遭遇卡获得涌动")
        ctx.extra["overzealous_drawn"] = drawn

        inv.discard.append("overzealous_lv0")
