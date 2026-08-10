"""Accursed Fate (Level 0) — Neutral Treachery, Weakness.
显现：受到2点恐惧。在战役日志中记录"the hour is nigh"。若已记录过，
将诅咒命运从你的牌组中移除，从牌库收藏中找出丧钟敲响，置于你的牌组底。

简化说明：
- 战役日志以 scenario.vars["campaign_log"]（list）近似（引擎无跨局日志存储）。
- "从牌组移除"按移出游戏处理，记入 scenario.vars["removed_from_game"]
  （与 stars_of_hyades_lv0 同一惯例）。
- 丧钟敲响（the_bell_tolls_lv0）数据存在时直接置于牌组底。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority

CAMPAIGN_LOG_ENTRY = "the hour is nigh"


class AccursedFate(CardImplementation):
    card_id = "accursed_fate_lv0"

    @on_event(GameEvent.CARD_DRAWN, priority=TimingPriority.WHEN)
    def revelation(self, ctx):
        if ctx.extra.get("card_id") != "accursed_fate_lv0":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if "accursed_fate_lv0" in inv.hand:
            inv.hand.remove("accursed_fate_lv0")

        inv.horror += 2  # 直接恐惧（不分配）

        campaign_log = ctx.game_state.scenario.vars.setdefault("campaign_log", [])
        if CAMPAIGN_LOG_ENTRY in campaign_log:
            # 已记录过：移出游戏，找出丧钟敲响置于牌组底
            ctx.game_state.scenario.vars.setdefault(
                "removed_from_game", []).append("accursed_fate_lv0")
            inv.deck.append("the_bell_tolls_lv0")
            ctx.extra["accursed_fate_upgraded"] = True
            ctx.game_state.log_effect(
                "🔔 诅咒命运：时刻已至——丧钟敲响置于牌组底")
        else:
            campaign_log.append(CAMPAIGN_LOG_ENTRY)
            inv.discard.append("accursed_fate_lv0")
