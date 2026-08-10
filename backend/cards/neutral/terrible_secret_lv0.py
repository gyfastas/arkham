"""Terrible Secret (Level 0) — Neutral Treachery, Weakness (Diana Stanley). (05015)
显现 - 若戴安娜·斯坦利下没有卡牌，将可怕秘密洗回你的牌组。否则，戴安娜·
斯坦利下的每张卡牌，你必须丢弃该卡或受到1点恐惧。不能被取消。

简化说明：
- "戴安娜下的卡牌"存放在 scenario.vars["beneath_{investigator_id}"]
  （the_painted_world_lv0 / stars_of_hyades_lv0 同一惯例），由戴安娜能力
  写入。
- 每张卡的选择（丢弃或受恐惧）简化为自动受1点恐惧（官方为玩家逐张选择）；
  会话层可传 choices 列表（与卡等长的 "discard"/"horror"）覆盖。
"""

import random

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


def beneath_key(investigator_id: str) -> str:
    return f"beneath_{investigator_id}"


class TerribleSecret(CardImplementation):
    card_id = "terrible_secret_lv0"

    @on_event(GameEvent.CARD_DRAWN, priority=TimingPriority.WHEN)
    def revelation(self, ctx):
        if ctx.extra.get("card_id") != "terrible_secret_lv0":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if "terrible_secret_lv0" in inv.hand:
            inv.hand.remove("terrible_secret_lv0")

        beneath = ctx.game_state.scenario.vars.get(beneath_key(inv.investigator_id), [])
        if not beneath:
            # 戴安娜下没有卡牌：洗回牌组
            inv.deck.append("terrible_secret_lv0")
            random.shuffle(inv.deck)
            ctx.extra["terrible_secret_shuffled"] = True
            return

        choices = ctx.extra.get("choices")
        results = []
        for i, cid in enumerate(list(beneath)):
            # 简化：缺省受1点恐惧（官方为玩家选择丢弃或受恐惧）
            choice = choices[i] if choices and i < len(choices) else "horror"
            if choice == "discard":
                beneath.remove(cid)
                inv.discard.append(cid)
                results.append(("discard", cid))
            else:
                inv.horror += 1
                results.append(("horror", cid))
        inv.discard.append("terrible_secret_lv0")
        ctx.extra["terrible_secret_results"] = results
