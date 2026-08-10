"""Ward of Protection (Level 2) — Mystic Event. (03270)
快速。在任意地点的一位调查员抽取一张非弱点诡计卡时打出。
取消该卡牌的显现效果。然后，受到1点恐惧。

简化说明：
- 自动触发：神话阶段抽到非弱点诡计卡时，若任意调查员手牌中有本卡，自动由
  持有者打出（优先抽牌者本人）、支付费用、标记
  scenario.vars["cancelled_encounter"]，由会话层跳过结算（同 lv0 惯例）。
- lv0 仅响应持有者自己抽牌；lv2 响应任意调查员抽牌（恐惧由持有者承受）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import CardType, GameEvent, TimingPriority


class WardOfProtectionLv2(CardImplementation):
    card_id = "ward_of_protection_lv2"

    @on_event(GameEvent.ENCOUNTER_CARD_DRAWN, priority=TimingPriority.WHEN)
    def cancel_revelation(self, ctx):
        card_id = ctx.extra.get("card_id")
        if not card_id:
            return

        cd = ctx.game_state.get_card_data(card_id)
        # 仅对非弱点诡计卡生效
        if cd is None or cd.type != CardType.TREACHERY:
            return
        if getattr(cd, "subtype", "") == "weakness" or "weakness" in (cd.traits or []):
            return

        # 持有者：优先抽牌者本人，其次任意手牌中有本卡的调查员
        holder = None
        drawer = ctx.game_state.get_investigator(ctx.investigator_id)
        if drawer is not None and self.card_id in drawer.hand:
            holder = drawer
        else:
            for candidate in ctx.game_state.investigators.values():
                if self.card_id in candidate.hand:
                    holder = candidate
                    break
        if holder is None:
            return

        ward_cd = ctx.game_state.get_card_data(self.card_id)
        cost = (getattr(ward_cd, "cost", 1) or 1) if ward_cd else 1
        if holder.resources < cost:
            return

        holder.resources -= cost
        holder.hand.remove(self.card_id)
        holder.discard.append(self.card_id)
        holder.horror += 1  # 然后受到1点恐惧
        ctx.game_state.scenario.vars["cancelled_encounter"] = card_id
        ctx.extra["ward_of_protection_cancelled"] = card_id
        ctx.extra["ward_of_protection_holder"] = holder.investigator_id
