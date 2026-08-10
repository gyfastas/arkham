"""Bought in Blood (Level 0) — Neutral Treachery, Weakness.
显现：你必须弃掉你控制的1个[[Ally]]支援，或弃掉你手牌中每张[[Ally]]支援。
若没有支援因此被弃掉，将血债血偿洗回你的牌组。

简化说明：
- 二选一自动判定：场上控制盟友则弃掉第一个盟友支援；否则弃掉手牌中
  所有盟友；两者皆无则洗回牌组（官方为玩家选择弃场上盟友或清空手牌盟友）。
"""

import random

from backend.cards._shared import defeat_asset
from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class BoughtInBlood(CardImplementation):
    card_id = "bought_in_blood_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._bus = None

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus

    @on_event(GameEvent.CARD_DRAWN, priority=TimingPriority.WHEN)
    def revelation(self, ctx):
        if ctx.extra.get("card_id") != "bought_in_blood_lv0":
            return
        game_state = ctx.game_state
        inv = game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if "bought_in_blood_lv0" in inv.hand:
            inv.hand.remove("bought_in_blood_lv0")

        discarded_any = False

        # 场上的盟友支援（弃第一个）
        ally_inst_id = None
        for inst_id in list(inv.play_area):
            inst = game_state.get_card_instance(inst_id)
            cd = game_state.get_card_data(inst.card_id) if inst else None
            if cd is not None and "ally" in (cd.traits or []):
                ally_inst_id = inst_id
                break
        if ally_inst_id is not None:
            defeat_asset(game_state, self._bus, ally_inst_id)
            discarded_any = True
            ctx.extra["bought_in_blood_discarded_play"] = ally_inst_id
        else:
            # 手牌中的所有盟友
            hand_allies = [
                cid for cid in list(inv.hand)
                if (cd := game_state.get_card_data(cid)) is not None
                and "ally" in (cd.traits or [])
            ]
            for cid in hand_allies:
                inv.hand.remove(cid)
                inv.discard.append(cid)
                discarded_any = True
            if hand_allies:
                ctx.extra["bought_in_blood_discarded_hand"] = hand_allies

        if not discarded_any:
            # 无支援被弃：洗回牌组
            inv.deck.append("bought_in_blood_lv0")
            random.shuffle(inv.deck)
            ctx.extra["bought_in_blood_shuffled_back"] = True
            game_state.log_effect("🩸 血债血偿：无盟友可弃，洗回牌组")
        else:
            inv.discard.append("bought_in_blood_lv0")
