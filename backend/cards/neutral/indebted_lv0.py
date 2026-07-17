"""Indebted — Neutral Treachery, Basic Weakness.
永久。
每次游戏开始时，你少获得2个资源。

简化说明：
- "永久"意味着开局即生效；引擎中实现为：第一轮开始时（含被抽到时）少2资源，
  并放入威胁区域作为在场标记。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class Indebted(CardImplementation):
    card_id = "indebted_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._applied = False

    @on_event(GameEvent.CARD_DRAWN, priority=TimingPriority.WHEN)
    def revelation(self, ctx):
        if ctx.extra.get("card_id") != "indebted_lv0":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if "indebted_lv0" in inv.hand:
            inv.hand.remove("indebted_lv0")
        self._place(ctx.game_state, inv)
        self._apply_penalty(inv)

    @on_event(GameEvent.ROUND_BEGINS, priority=TimingPriority.WHEN)
    def apply_on_first_round(self, ctx):
        """开局生效：第一轮开始时若未应用则少2资源。"""
        if self._applied:
            return
        for inv in ctx.game_state.investigators.values():
            # 只对牌组中包含本卡的调查员生效（简化：牌堆/手牌/弃牌堆含有即算）
            if (
                "indebted_lv0" in inv.deck
                or "indebted_lv0" in inv.hand
                or "indebted_lv0" in inv.discard
            ):
                if "indebted_lv0" in inv.deck:
                    inv.deck.remove("indebted_lv0")
                elif "indebted_lv0" in inv.hand:
                    inv.hand.remove("indebted_lv0")
                self._place(ctx.game_state, inv)
                self._apply_penalty(inv)

    def _apply_penalty(self, inv) -> None:
        if self._applied:
            return
        inv.resources = max(0, inv.resources - 2)
        self._applied = True

    @staticmethod
    def _place(game_state, inv) -> None:
        from backend.models.state import CardInstance
        inst_id = game_state.next_instance_id()
        ci = CardInstance(
            instance_id=inst_id,
            card_id="indebted_lv0",
            owner_id=inv.investigator_id,
            controller_id=inv.investigator_id,
        )
        game_state.cards_in_play[inst_id] = ci
        inv.threat_area.append(inst_id)
