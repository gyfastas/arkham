"""Glimpse the Unthinkable (Level 5) — Seeker Event. (05318)
将你手牌中任意数量的非弱点卡牌混洗入你的牌堆。抽取卡牌，直到手牌数量
达到上限。将窥看不思议之事移出游戏。

简化说明：
- 混洗目标默认为你手牌中全部非弱点卡牌（通常最优；官方为玩家自选），
  可用 ctx.extra["shuffle_card_ids"] 显式指定；
- 手牌上限取引擎常量 HAND_SIZE_LIMIT=8；
- 抽牌直接自牌堆顶抽取（不发 CARD_DRAWN，与 cryptic_research 一致；
  抽到弱点不触发揭示，已知简化）；
- "移出游戏"：引擎在 CARD_PLAYED 结算后才把事件放入弃牌堆，无拦截钩子，
  故延迟到 ROUND_ENDS 从弃牌堆移出（记录在 scenario.vars["removed_from_game"]，
  与 eidetic_memory 一致）。
"""

import random

from backend.cards.base import CardImplementation, on_event
from backend.engine.phase_upkeep import HAND_SIZE_LIMIT
from backend.models.enums import GameEvent, TimingPriority
from backend.models.state import is_weakness_card


class GlimpseTheUnthinkable(CardImplementation):
    card_id = "glimpse_the_unthinkable_lv5"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._remove_pending: str | None = None

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def shuffle_and_redraw(self, ctx):
        if ctx.extra.get("card_id") != self.card_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        self._remove_pending = ctx.investigator_id

        # 任意数量非弱点手牌混洗入牌堆（默认全部非弱点）
        shuffle_ids = ctx.extra.get("shuffle_card_ids")
        if shuffle_ids is None:
            shuffle_ids = [
                cid for cid in inv.hand
                if not is_weakness_card(ctx.game_state.get_card_data(cid))
            ]
        else:
            shuffle_ids = [
                cid for cid in shuffle_ids
                if cid in inv.hand
                and not is_weakness_card(ctx.game_state.get_card_data(cid))
            ]
        for cid in shuffle_ids:
            inv.hand.remove(cid)
        inv.deck.extend(shuffle_ids)
        random.shuffle(inv.deck)

        # 抽取卡牌，直到手牌数量达到上限
        drawn = 0
        while len(inv.hand) < HAND_SIZE_LIMIT and inv.deck:
            inv.hand.append(inv.deck.pop(0))
            drawn += 1
        ctx.extra["glimpse_shuffled"] = len(shuffle_ids)
        ctx.extra["glimpse_drawn"] = drawn
        ctx.game_state.log_effect(
            f"🔮 窥看不思议之事：混洗{len(shuffle_ids)}张回牌堆，抽取{drawn}张"
        )

    @on_event(GameEvent.ROUND_ENDS, priority=TimingPriority.AFTER)
    def remove_from_game(self, ctx):
        """本卡移出游戏（引擎出牌结算后才入弃牌堆，延迟清理）。"""
        if self._remove_pending is None:
            return
        inv = ctx.game_state.get_investigator(self._remove_pending)
        self._remove_pending = None
        if inv is not None and self.card_id in inv.discard:
            inv.discard.remove(self.card_id)
            ctx.game_state.scenario.vars.setdefault(
                "removed_from_game", []).append(self.card_id)
