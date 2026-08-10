"""Rookie Mistake (Level 0) — Neutral Treachery, Weakness. (06007)
显现 - 丢弃你控制的每张上有伤害或恐惧的支援卡。若没有支援卡被本效果丢弃，
将新手错误洗回你的牌组。
"""

import random

from backend.cards.base import CardImplementation, on_event
from backend.cards._shared import defeat_asset
from backend.models.enums import CardType, GameEvent, TimingPriority


class RookieMistake(CardImplementation):
    card_id = "rookie_mistake_lv0"

    @on_event(GameEvent.CARD_DRAWN, priority=TimingPriority.WHEN)
    def revelation(self, ctx):
        if ctx.extra.get("card_id") != "rookie_mistake_lv0":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if "rookie_mistake_lv0" in inv.hand:
            inv.hand.remove("rookie_mistake_lv0")

        discarded = []
        for iid in list(inv.play_area):
            inst = ctx.game_state.get_card_instance(iid)
            if inst is None:
                continue
            cd = ctx.game_state.get_card_data(inst.card_id)
            if cd is None or cd.type != CardType.ASSET:
                continue
            if inst.damage > 0 or inst.horror > 0:
                defeat_asset(ctx.game_state, getattr(self, "_bus", None), iid)
                discarded.append(inst.card_id)

        if discarded:
            inv.discard.append("rookie_mistake_lv0")
        else:
            inv.deck.append("rookie_mistake_lv0")
            random.shuffle(inv.deck)
        ctx.extra["rookie_mistake_discarded"] = discarded

    def register(self, bus, instance_id: str) -> None:
        self._bus = bus
        super().register(bus, instance_id)
