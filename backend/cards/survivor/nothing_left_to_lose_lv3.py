"""Nothing Left to Lose (Level 3) — Survivor Event. (06284)
If you have fewer than 5 resources, gain resources until you have 5
resources.
If you have fewer than 5 cards in your hand, draw cards until you have 5
cards in your hand.
Remove Nothing Left to Lose from the game.

简化说明：
- 抽牌直接取牌堆顶（不经 draw_hooks 的弱点显现流程，与 madame_labranche
  等既有抽牌实现一致，从简）；牌堆抽空即停（不触发洗牌重抽+恐惧）。
- 移出游戏：引擎在事件结算后将其置入弃牌堆，本实现登记
  scenario.vars["removed_from_game"] 并在随后的 ACTION_PERFORMED /
  ROUND_ENDS 从弃牌堆清除（引擎无"移出游戏"区，见报告）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority

_TARGET = 5


class NothingLeftToLose(CardImplementation):
    card_id = "nothing_left_to_lose_lv3"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._remove_pending: str | None = None  # 待移出游戏的持有者

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def refill(self, ctx):
        if ctx.extra.get("card_id") != self.card_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return

        if inv.resources < _TARGET:
            gained = _TARGET - inv.resources
            inv.resources = _TARGET
            ctx.extra["nltt_resources_gained"] = gained
        drawn = 0
        while len(inv.hand) < _TARGET and inv.deck:
            inv.hand.append(inv.deck.pop(0))
            drawn += 1
        if drawn:
            ctx.extra["nltt_cards_drawn"] = drawn
        ctx.game_state.log_effect(
            f"💸 孤注一掷：补至{_TARGET}资源/{_TARGET}手牌，移出游戏")
        self._remove_pending = inv.investigator_id

    @on_event(GameEvent.ACTION_PERFORMED, priority=TimingPriority.AFTER)
    def sweep_after_action(self, ctx):
        self._sweep(ctx)

    @on_event(GameEvent.ROUND_ENDS, priority=TimingPriority.AFTER)
    def sweep_after_round(self, ctx):
        self._sweep(ctx)

    def _sweep(self, ctx) -> None:
        """引擎结算后将本卡从弃牌堆移出游戏。"""
        inv_id = self._remove_pending
        if inv_id is None:
            return
        inv = ctx.game_state.get_investigator(inv_id)
        if inv is not None and self.card_id in inv.discard:
            inv.discard.remove(self.card_id)
            ctx.game_state.scenario.vars.setdefault(
                "removed_from_game", []).append(self.card_id)
        self._remove_pending = None
