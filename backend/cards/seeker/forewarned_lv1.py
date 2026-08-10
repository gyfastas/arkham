"""Forewarned (Level 1) — Seeker Event, Fast.
快速。在你抽取1张非弱点诡计卡时打出。
将你的1条线索放置到你所在地点。然后，取消该卡的显现效果。

简化说明：
- 自动触发：抽到非弱点诡计卡时，若手牌中有预知且你持有至少1条线索，
  自动打出（费用0）、放置1条线索到所在地点、
  标记 scenario.vars["cancelled_encounter"]，由会话层跳过结算
  （与 Ward of Protection 同模式）；
- 没有线索可放置时不触发（"Then"要求先完成放置）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import CardType, GameEvent, TimingPriority
from backend.models.state import is_weakness_card


class Forewarned(CardImplementation):
    card_id = "forewarned_lv1"

    @on_event(GameEvent.ENCOUNTER_CARD_DRAWN, priority=TimingPriority.WHEN)
    def cancel_revelation(self, ctx):
        card_id = ctx.extra.get("card_id")
        if not card_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.card_id not in inv.hand:
            return

        cd = ctx.game_state.get_card_data(card_id)
        # 仅对非弱点诡计卡生效
        if cd is None or cd.type != CardType.TREACHERY or is_weakness_card(cd):
            return
        # 需要至少1条线索用于放置
        if inv.clues < 1:
            return

        inv.hand.remove(self.card_id)
        inv.discard.append(self.card_id)
        inv.clues -= 1
        loc = ctx.game_state.get_location(inv.location_id)
        if loc is not None:
            loc.clues += 1

        ctx.game_state.scenario.vars["cancelled_encounter"] = card_id
        ctx.extra["forewarned_cancelled"] = card_id
        ctx.game_state.log_effect(
            f"🔮 预知：放置1条线索到所在地点，取消"
            f"【{ctx.game_state.card_name(card_id)}】的显现效果"
        )
