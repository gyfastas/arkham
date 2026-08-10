"""Dark Insight (Level 0) — Neutral Event (Diana Stanley deck only).
快速。当1名你所在地点的调查员抽取1张遭遇卡或1张弱点时打出。
取消该卡牌的所有效果，并将其洗回其牌组。（不要抽新牌替代。）

简化说明：
- 在手牌中持续注册（persistent_in_hand）；触发时自动打出（支付2费用、
  入弃牌堆），官方为玩家选择打出时机——这里自动取消首张可取消的抽牌。
- 弱点（CARD_DRAWN）：取消后该弱点不再结算显现效果（事件循环在
  ctx.cancelled 后中断；黑暗洞察在手牌中的注册早于新抽弱点的临时注册，
  WHEN 优先级相同按注册顺序先执行），牌洗回其持有者牌组。
- 遭遇卡（ENCOUNTER_CARD_DRAWN）：洗回遭遇牌堆并取消；但 MythosPhase
  在事件后无条件把该卡加入遭遇弃牌堆（不尊重取消——引擎缺口），生产环境
  需引擎配合修复。
"""

import random

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority
from backend.models.state import is_weakness_card


class DarkInsight(CardImplementation):
    card_id = "dark_insight_lv0"
    persistent_in_hand = True  # 在手牌中持续生效

    def _find_holder(self, game_state):
        """手牌中含黑暗洞察的调查员。"""
        for inv in game_state.investigators.values():
            if "dark_insight_lv0" in inv.hand:
                return inv
        return None

    def _try_cancel(self, ctx, drawn_card_id, deck_getter):
        holder = self._find_holder(ctx.game_state)
        if holder is None or holder.resources < 2:
            return False
        target_inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if target_inv is None or target_inv.location_id != holder.location_id:
            return False

        # 支付费用并弃掉黑暗洞察
        holder.resources -= 2
        holder.hand.remove("dark_insight_lv0")
        holder.discard.append("dark_insight_lv0")

        # 洗回其牌组
        deck = deck_getter()
        if deck is not None:
            deck.append(drawn_card_id)
            random.shuffle(deck)

        ctx.cancel()  # 取消该卡牌的所有效果
        ctx.extra["dark_insight_cancelled"] = drawn_card_id
        ctx.game_state.log_effect(f"🌑 黑暗洞察：取消并洗回【{drawn_card_id}】")
        return True

    @on_event(GameEvent.CARD_DRAWN, priority=TimingPriority.WHEN)
    def cancel_weakness_draw(self, ctx):
        """你所在地点的调查员抽到弱点时：自动打出，取消并洗回其牌组。"""
        card_id = ctx.extra.get("card_id")
        if card_id in (None, "dark_insight_lv0"):
            return
        if not is_weakness_card(ctx.game_state.get_card_data(card_id)):
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or card_id not in inv.hand:
            return

        def _deck():
            if card_id in inv.hand:
                inv.hand.remove(card_id)
            return inv.deck

        self._try_cancel(ctx, card_id, _deck)

    @on_event(GameEvent.ENCOUNTER_CARD_DRAWN, priority=TimingPriority.WHEN)
    def cancel_encounter_draw(self, ctx):
        """你所在地点的调查员抽到遭遇卡时：自动打出，取消并洗回遭遇牌堆。"""
        card_id = ctx.extra.get("card_id")
        if card_id is None:
            return

        def _deck():
            return ctx.game_state.scenario.encounter_deck

        self._try_cancel(ctx, card_id, _deck)
