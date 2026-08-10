"""Calling in Favors (Level 0) — Neutral Event.
选择一张你控制的[[盟友]]支援卡并返回手牌。然后，在你牌堆顶9张卡牌中查找
并打出一张[[盟友]]支援卡，其费用降低X点（X为返回手牌的盟友费用）。混洗牌堆。

简化说明：
- 目标选择为自动：返回你控制的第一张盟友；打出牌堆顶9张中的第一张盟友
  （官方为玩家选择）。
- 若打出费用（减免后）超过现有资源，则不打出该盟友（留在牌堆并混洗）。
- 打出的盟友直接放入 play_area；其卡牌能力的注册/激活需要会话层接线
  （卡牌 handler 无法访问 CardRegistry，见 actions._play_asset）。
"""

import random

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import CardType, GameEvent, TimingPriority
from backend.models.state import CardInstance


class CallingInFavors(CardImplementation):
    card_id = "calling_in_favors_lv0"

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.AFTER)
    def resolve(self, ctx):
        if ctx.extra.get("card_id") != "calling_in_favors_lv0":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return

        # 1. 返回一张你控制的盟友到手牌
        returned_cost = 0
        returned_id = None
        for iid in list(inv.play_area):
            inst = ctx.game_state.get_card_instance(iid)
            cd = ctx.game_state.get_card_data(inst.card_id) if inst else None
            if cd is not None and cd.type == CardType.ASSET and "ally" in (cd.traits or []):
                inv.play_area.remove(iid)
                ctx.game_state.cards_in_play.pop(iid, None)
                inv.hand.append(inst.card_id)
                returned_cost = cd.cost or 0
                returned_id = inst.card_id
                break
        if returned_id is None:
            # 没有可返回的盟友，效果不发动（官方需选择一张你控制的盟友）
            ctx.extra["calling_in_favors"] = "no_ally"
            return

        # 2. 牌堆顶9张中查找盟友并打出（费用降低X）
        played_id = None
        for cid in inv.deck[:9]:
            cd = ctx.game_state.get_card_data(cid)
            if cd is not None and cd.type == CardType.ASSET and "ally" in (cd.traits or []):
                cost = max(0, (cd.cost or 0) - returned_cost)
                if inv.resources >= cost:
                    inv.resources -= cost
                    inv.deck.remove(cid)
                    inst_id = ctx.game_state.next_instance_id()
                    ci = CardInstance(
                        instance_id=inst_id,
                        card_id=cid,
                        owner_id=inv.investigator_id,
                        controller_id=inv.investigator_id,
                        slot_used=list(cd.slots or []),
                    )
                    if cd.uses:
                        ci.uses = dict(cd.uses)
                    ctx.game_state.cards_in_play[inst_id] = ci
                    inv.play_area.append(inst_id)
                    played_id = cid
                break

        # 3. 混洗牌堆
        random.shuffle(inv.deck)

        ctx.extra["calling_in_favors"] = {
            "returned": returned_id,
            "discount": returned_cost,
            "played": played_id,
        }
        ctx.game_state.log_effect(
            f"📞 人情往来：收回【{ctx.game_state.card_name(returned_id)}】"
            + (f"，打出【{ctx.game_state.card_name(played_id)}】" if played_id else "")
        )
