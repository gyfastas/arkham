"""Doomed (Level 0) — Neutral Treachery, Basic Weakness. (Campaign Mode only)
显现：受到1点恐惧。在战役日志中记录"doom approaches"。若已记录过，
将厄运难逃从你的牌组中移除，从牌库收藏中找出诅咒命运，置于你的牌组底。

简化说明：
- 战役日志以 scenario.vars["campaign_log"]（list）近似（引擎无跨局日志存储）。
- "从牌组移除"按移出游戏处理，记入 scenario.vars["removed_from_game"]。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority

CAMPAIGN_LOG_ENTRY = "doom approaches"


class Doomed(CardImplementation):
    card_id = "doomed_lv0"

    @on_event(GameEvent.CARD_DRAWN, priority=TimingPriority.WHEN)
    def revelation(self, ctx):
        if ctx.extra.get("card_id") != "doomed_lv0":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if "doomed_lv0" in inv.hand:
            inv.hand.remove("doomed_lv0")

        inv.horror += 1  # 直接恐惧（不分配）

        campaign_log = ctx.game_state.scenario.vars.setdefault("campaign_log", [])
        if CAMPAIGN_LOG_ENTRY in campaign_log:
            # 已记录过：移出游戏，找出诅咒命运置于牌组底
            ctx.game_state.scenario.vars.setdefault(
                "removed_from_game", []).append("doomed_lv0")
            inv.deck.append("accursed_fate_lv0")
            ctx.extra["doomed_upgraded"] = True
            ctx.game_state.log_effect("⏳ 厄运难逃：末日逼近——诅咒命运置于牌组底")
        else:
            campaign_log.append(CAMPAIGN_LOG_ENTRY)
            inv.discard.append("doomed_lv0")
