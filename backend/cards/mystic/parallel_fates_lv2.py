"""Parallel Fates (Level 2) — Mystic Event. (Augury)
查看一位调查员牌库或遭遇牌堆顶的6张牌。你可以将它们以任意顺序放回该牌堆顶，
或将它们洗入该牌堆。如果你查看的是调查员的牌库，该调查员可以抽1张牌。

简化说明：
- 选项经 CARD_PLAYED 的 ctx.extra 传参：target_investigator_id /
  target_encounter_deck / shuffle=True / order（顶6张新顺序索引）/
  draw=False（不抽）。默认：查看自己牌库顶6张、保持原顺序放回、抽1张。
- "洗入该牌堆"：将顶6张与其余牌一起洗牌。
"""

import random

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority

LOOK_COUNT = 6


class ParallelFates(CardImplementation):
    card_id = "parallel_fates_lv2"

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def resolve(self, ctx):
        if ctx.extra.get("card_id") != self.card_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return

        owner = None
        if ctx.extra.get("target_encounter_deck"):
            deck = ctx.game_state.scenario.encounter_deck
        else:
            owner = ctx.game_state.get_investigator(
                ctx.extra.get("target_investigator_id") or ctx.investigator_id)
            if owner is None:
                return
            deck = owner.deck
        if not deck:
            return

        n = min(LOOK_COUNT, len(deck))
        looked = deck[:n]

        if ctx.extra.get("shuffle"):
            # 洗入该牌堆
            rest = deck[n:]
            rest.extend(looked)
            random.shuffle(rest)
            deck[:] = rest
            ctx.extra["parallel_fates_shuffled"] = True
        else:
            order = ctx.extra.get("order")
            if order and sorted(order) == list(range(n)):
                deck[:n] = [looked[i] for i in order]
                ctx.extra["parallel_fates_reordered"] = True
            # 默认：保持原顺序放回顶（无操作）

        # 查看调查员牌库：可抽1张（默认抽；draw=False 不抽）
        if owner is not None and ctx.extra.get("draw", True) and owner.deck:
            owner.hand.append(owner.deck.pop(0))
            ctx.extra["parallel_fates_drew"] = True
