"""Ward of Protection (Level 0) — Mystic Event.
快速。在你抽取一张非弱点诡计卡时打出。取消该卡的所有效果，弃置它。然后，受到1点恐惧。

简化说明：
- 自动触发：神话阶段抽到非弱点诡计卡时，若手牌中有守护结界，自动打出
  （支付费用）、标记 scenario.vars["cancelled_encounter"]，由会话层跳过结算。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import CardType, GameEvent, TimingPriority


class WardOfProtection(CardImplementation):
    card_id = "ward_of_protection_lv0"

    @on_event(GameEvent.ENCOUNTER_CARD_DRAWN, priority=TimingPriority.WHEN)
    def cancel_revelation(self, ctx):
        card_id = ctx.extra.get("card_id")
        if not card_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or "ward_of_protection_lv0" not in inv.hand:
            return

        cd = ctx.game_state.get_card_data(card_id)
        # 仅对非弱点诡计卡生效
        if cd is None or cd.type != CardType.TREACHERY:
            return
        if getattr(cd, "subtype", "") == "weakness" or "weakness" in (cd.traits or []):
            return

        cost = cd.cost or 1
        ward_cd = ctx.game_state.get_card_data("ward_of_protection_lv0")
        cost = getattr(ward_cd, "cost", 1) or 1 if ward_cd else 1
        if inv.resources < cost:
            return

        inv.resources -= cost
        inv.hand.remove("ward_of_protection_lv0")
        inv.discard.append("ward_of_protection_lv0")
        inv.horror += 1  # 然后受到1点恐惧
        ctx.game_state.scenario.vars["cancelled_encounter"] = card_id
        ctx.extra["ward_of_protection_cancelled"] = card_id
