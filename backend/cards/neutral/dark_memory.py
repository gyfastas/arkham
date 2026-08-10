"""Dark Memory — Neutral Event, Signature Weakness (Agnes Baker).
阿格尼丝·贝克牌组专用。
在当前密谋上放置1个毁灭标记。（此效果可能导致当前密谋推进。）
强制 - 如果你回合结束时手牌中有黑暗记忆：展示该牌并受到2点恐惧。

实现说明：
- 卡面无弃牌语句：回合结束触发后黑暗记忆留在手牌中，之后每个回合结束
  都会重复触发（persistent_in_hand = True，保持抽到时的注册）。
- 放置毁灭标记后立即进行毁灭阈值检查（经 MythosPhase._check_doom_threshold，
  与 official_core 剧本内放置毁灭的处理一致），可能导致密谋推进。
- 抽到（CARD_DRAWN）与从手牌打出（CARD_PLAYED，事件类型，费用2）都会
  放置毁灭标记；同一事件上下文用 extra 标记去重，避免重复注册时双倍结算。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class DarkMemory(CardImplementation):
    card_id = "dark_memory"
    persistent_in_hand = True  # 强制效果在手牌中持续生效

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._bus = None

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus  # 毁灭阈值检查需要经事件总线通知密谋推进

    @on_event(GameEvent.CARD_DRAWN, priority=TimingPriority.WHEN)
    def revelation(self, ctx):
        if ctx.extra.get("card_id") != "dark_memory":
            return
        self._place_doom(ctx)

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def played(self, ctx):
        """从手牌打出黑暗记忆（事件，费用2）：同样放置1个毁灭标记。"""
        if ctx.extra.get("card_id") != "dark_memory":
            return
        self._place_doom(ctx)

    def _place_doom(self, ctx) -> None:
        """在当前密谋上放置1个毁灭标记，并立即检查密谋推进。"""
        if ctx.extra.get("dark_memory_doom_placed"):
            return  # 同一事件上下文中已有注册实例结算过
        ctx.extra["dark_memory_doom_placed"] = True
        scenario = ctx.game_state.scenario
        scenario.doom_on_agenda += 1
        if self._bus is not None:
            from backend.engine.phase_mythos import MythosPhase
            MythosPhase(ctx.game_state, self._bus)._check_doom_threshold()

    @on_event(GameEvent.INVESTIGATOR_TURN_ENDS, priority=TimingPriority.AFTER)
    def turn_end_horror(self, ctx):
        """回合结束时手牌中有黑暗记忆：展示并受到2点恐惧（牌留在手牌）。"""
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if "dark_memory" not in inv.hand:
            return
        if ctx.extra.get("dark_memory_horror_taken"):
            return  # 防止重复注册时多次触发
        ctx.extra["dark_memory_horror_taken"] = True
        inv.horror += 2  # 直接恐惧（不分配；引擎层直接伤害不判负的已知问题待统一处理）
