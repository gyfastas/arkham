"""Dark Memory — Neutral Treachery, Signature Weakness (Agnes Baker).
阿格尼丝·贝克牌组专用。
在当前密谋上放置1个毁灭标记。（此效果可能导致当前密谋推进。）
强制 - 如果你回合结束时手牌中有黑暗记忆：展示该牌并受到2点恐惧。

简化说明：
- 黑暗记忆留在手牌中（persistent_in_hand = True，保持抽到时的注册），
  回合结束触发后弃掉并自我注销。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class DarkMemory(CardImplementation):
    card_id = "dark_memory"
    persistent_in_hand = True  # 强制效果在手牌中持续生效

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._spent = False

    @on_event(GameEvent.CARD_DRAWN, priority=TimingPriority.WHEN)
    def revelation(self, ctx):
        if ctx.extra.get("card_id") != "dark_memory":
            return
        # 在当前密谋上放置1个毁灭标记
        scenario = ctx.game_state.scenario
        scenario.doom_on_agenda += 1
        ctx.extra["dark_memory_doom_placed"] = True

    @on_event(GameEvent.INVESTIGATOR_TURN_ENDS, priority=TimingPriority.AFTER)
    def turn_end_horror(self, ctx):
        """回合结束时手牌中有黑暗记忆：展示并受到2点恐惧，然后弃掉。"""
        if self._spent:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if "dark_memory" not in inv.hand:
            return
        inv.hand.remove("dark_memory")
        inv.discard.append("dark_memory")
        inv.horror += 2  # 直接恐惧（不分配）
        self._spent = True  # 触发后失效（handler 中无法安全访问 bus 注销）
