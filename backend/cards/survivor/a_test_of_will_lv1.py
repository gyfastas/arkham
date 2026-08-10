"""A Test of Will (Level 1) — Survivor Event.
快速。在你所在地点的一位调查员抽出一张非弱点诡计卡时打出。
取消该卡牌的显现效果。放逐意志考验。

简化说明：
- 从手牌中自动触发（同 ward_of_protection 模式）：你所在地点的调查员
  抽到非弱点诡计卡时，若同地点任一调查员手牌中有意志考验且资源足够，
  自动打出、标记 scenario.vars["cancelled_encounter"]，由会话层跳过
  显现结算（官方为玩家自行选择打出时机）。
- 放逐：引擎无放逐区，卡片从手牌移除后登记在
  scenario.vars["exiled_cards"]，不进入弃牌堆（引擎缺口，见报告）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import CardType, GameEvent, TimingPriority
from backend.models.state import is_weakness_card


class ATestOfWill(CardImplementation):
    card_id = "a_test_of_will_lv1"
    persistent_in_hand = True  # 在手牌中持续监听诡计抽取窗口

    @on_event(GameEvent.ENCOUNTER_CARD_DRAWN, priority=TimingPriority.WHEN)
    def cancel_revelation(self, ctx):
        card_id = ctx.extra.get("card_id")
        if not card_id or ctx.extra.get("a_test_of_will_cancelled"):
            return
        cd = ctx.game_state.get_card_data(card_id)
        # 仅对非弱点诡计卡生效
        if cd is None or cd.type != CardType.TREACHERY:
            return
        if is_weakness_card(cd) or "weakness" in (cd.traits or []):
            return

        drawer = ctx.game_state.get_investigator(ctx.investigator_id)
        if drawer is None:
            return
        # 你所在地点手持意志考验的调查员
        holder = None
        for cand in ctx.game_state.investigators.values():
            if cand.location_id != drawer.location_id:
                continue
            if self.card_id in cand.hand:
                holder = cand
                break
        if holder is None:
            return

        my_cd = ctx.game_state.get_card_data(self.card_id)
        cost = (getattr(my_cd, "cost", 1) or 1) if my_cd else 1
        if holder.resources < cost:
            return

        holder.resources -= cost
        holder.hand.remove(self.card_id)
        # 放逐（不进入弃牌堆）
        ctx.game_state.scenario.vars.setdefault(
            "exiled_cards", []).append(self.card_id)
        ctx.game_state.scenario.vars["cancelled_encounter"] = card_id
        ctx.extra["a_test_of_will_cancelled"] = card_id
        ctx.game_state.log_effect(
            f"🛡️ 意志考验：取消【{ctx.game_state.card_name(card_id)}】的显现效果，放逐")
