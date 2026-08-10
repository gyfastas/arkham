"""Tides of Fate (Level 0) — Mystic Event, fast. (07030)
快速。可在任意[fast]窗口或一轮开始时打出。
将混乱袋中所有[curse]标记替换为等量的[bless]标记。本轮结束时，将混乱袋中
所有[bless]标记替换为等量的[curse]标记。

简化说明：
- 混沌袋经 bind_chaos_bag 注入（事件经 actions._play_event 的
  activate_card 生产接线，测试可手动绑定）。
- 轮回换按卡面字面实现：袋中所有 bless 均换成 curse（包括原本就有的
  bless，不限于本次换入的）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import ChaosTokenType, GameEvent, TimingPriority


class TidesOfFate(CardImplementation):
    card_id = "tides_of_fate_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._bag = None
        self._played = False

    def bind_chaos_bag(self, chaos_bag) -> None:
        self._bag = chaos_bag

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def curse_to_bless(self, ctx):
        if ctx.extra.get("card_id") != self.card_id:
            return
        if self._bag is None:
            return
        count = self._bag.tokens.count(ChaosTokenType.CURSE)
        for _ in range(count):
            self._bag.remove(ChaosTokenType.CURSE)
            self._bag.add_token(ChaosTokenType.BLESS)
        self._played = True
        ctx.extra["tides_of_fate_swapped"] = count
        ctx.game_state.log_effect(
            f"🌊 命运潮汐：袋中{count}个[curse]替换为[bless]")

    @on_event(GameEvent.ROUND_ENDS, priority=TimingPriority.AFTER)
    def bless_to_curse(self, ctx):
        """本轮结束：袋中所有[bless]换回[curse]。"""
        if not self._played or self._bag is None:
            return
        count = self._bag.tokens.count(ChaosTokenType.BLESS)
        for _ in range(count):
            self._bag.remove(ChaosTokenType.BLESS)
            self._bag.add_token(ChaosTokenType.CURSE)
        ctx.game_state.log_effect(
            f"🌊 命运潮汐：轮次结束，{count}个[bless]换回[curse]")
        self._played = False
