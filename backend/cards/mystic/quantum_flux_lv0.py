"""Quantum Flux (Level 0) — Mystic Event. (03196)
将你的弃牌堆洗入你的牌库，并抽取1张卡牌。从游戏中移除量子通量。

简化说明：
- "从游戏中移除"记录在 scenario.vars["removed_from_game"]（引擎无独立移除区，
  同 abandoned_and_alone 惯例）。
- 打出时本卡在 CARD_PLAYED 结算后才进入弃牌堆（engine/actions._play_event），
  故移除分两步：打出时先尝试立即移除（覆盖测试直入弃牌堆的路径），
  再在下一个 ACTION_PERFORMED / ROUND_ENDS 时从弃牌堆补移除。
- 抽牌不触发抽到弱点等 CARD_DRAWN 钩子（卡牌代码拿不到 registry/draw_hooks
  入口——引擎缺口）。
"""

import random

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class QuantumFlux(CardImplementation):
    card_id = "quantum_flux_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._pending_remove = False

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def shuffle_and_draw(self, ctx):
        if ctx.extra.get("card_id") != self.card_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return

        # 弃牌堆洗入牌库
        if inv.discard:
            inv.deck.extend(inv.discard)
            inv.discard.clear()
        random.shuffle(inv.deck)

        # 抽1张牌
        if inv.deck:
            inv.hand.append(inv.deck.pop(0))
            ctx.extra["quantum_flux_drew"] = True

        # 从游戏中移除本卡（打出流程中本卡尚未入弃牌堆，此处覆盖已入弃牌堆的路径）
        self._pending_remove = True
        self._remove_from_game(ctx.game_state, inv)
        ctx.extra["quantum_flux_resolved"] = True

    @on_event(GameEvent.ACTION_PERFORMED, priority=TimingPriority.AFTER)
    @on_event(GameEvent.ROUND_ENDS, priority=TimingPriority.AFTER)
    def deferred_remove(self, ctx):
        """打出流程结算后本卡落入弃牌堆：补做移出游戏。"""
        if not self._pending_remove:
            return
        for inv in ctx.game_state.investigators.values():
            if self.card_id in inv.discard:
                self._remove_from_game(ctx.game_state, inv)
        self._pending_remove = False

    def _remove_from_game(self, game_state, inv) -> None:
        removed = False
        for zone in (inv.hand, inv.discard, inv.deck):
            while self.card_id in zone:
                zone.remove(self.card_id)
                removed = True
        if removed:
            game_state.scenario.vars.setdefault(
                "removed_from_game", []).append(self.card_id)
