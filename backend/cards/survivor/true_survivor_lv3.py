"""True Survivor (Level 3) — Survivor Event.
将你弃牌堆中的3张[[天性]]技能卡返回你的手牌。

简化说明：
- 目标选择简化：自动按弃牌堆顺序取前3张天性（Innate）技能卡
  （官方为玩家选择；弃牌堆不足3张时全取）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import CardType, GameEvent, TimingPriority

_MAX_RETURN = 3


class TrueSurvivor(CardImplementation):
    card_id = "true_survivor_lv3"

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def return_innate_skills(self, ctx):
        """将弃牌堆中至多3张天性技能卡返回手牌。"""
        if ctx.extra.get("card_id") != self.card_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        returned = []
        for cid in list(inv.discard):
            if len(returned) >= _MAX_RETURN:
                break
            cd = ctx.game_state.get_card_data(cid)
            if cd is None or cd.type != CardType.SKILL:
                continue
            if "innate" not in (cd.traits or []):
                continue
            inv.discard.remove(cid)
            inv.hand.append(cid)
            returned.append(cid)
        ctx.extra["true_survivor_returned"] = returned
        if returned:
            names = "、".join(ctx.game_state.card_name(c) for c in returned)
            ctx.game_state.log_effect(
                f"🏕️ 真正的生存者：{len(returned)}张天性技能卡返回手牌（{names}）")
