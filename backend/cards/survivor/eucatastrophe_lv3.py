"""Eucatastrophe (Level 3) — Survivor Event.
快速。在你将要被击败时打出。改为弃置你手牌中所有的弱点，恢复所有生命和理智，
获得3资源，结束你本回合。

简化说明：
- 从手牌中自动触发：你将要被击败时自动打出并取消击败。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class Eucatastrophe(CardImplementation):
    card_id = "eucatastrophe_lv3"

    @on_event(GameEvent.INVESTIGATOR_DEFEATED, priority=TimingPriority.WHEN)
    def cancel_defeat(self, ctx):
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or "eucatastrophe_lv3" not in inv.hand:
            return

        # 自动打出（取消击败）
        cd = ctx.game_state.get_card_data("eucatastrophe_lv3")
        cost = getattr(cd, "cost", 2) or 2 if cd else 2
        if inv.resources < cost:
            return
        inv.resources -= cost
        inv.hand.remove("eucatastrophe_lv3")
        inv.discard.append("eucatastrophe_lv3")

        # 弃置手牌中所有弱点
        weaknesses = []
        for cid in list(inv.hand):
            cd2 = ctx.game_state.get_card_data(cid)
            if cd2 and (getattr(cd2, "subtype", "") == "weakness"
                        or "weakness" in (cd2.traits or [])):
                inv.hand.remove(cid)
                inv.discard.append(cid)
                weaknesses.append(cid)

        # 恢复所有生命和理智，获得3资源，结束回合
        inv.damage = 0
        inv.horror = 0
        inv.resources += 3
        inv.actions_remaining = 0

        ctx.cancel()
        ctx.extra["eucatastrophe_saved"] = True
        ctx.extra["eucatastrophe_weaknesses"] = weaknesses
