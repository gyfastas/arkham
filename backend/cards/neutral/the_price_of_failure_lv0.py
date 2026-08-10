"""The Price of Failure (Level 0) — Neutral Treachery, Weakness (Pact).
显现：受到2点伤害和2点恐惧。在当前密谋上放置1个毁灭标记（此效果可能导致
当前密谋推进）。将失败的代价从你的牌组中移除。从牌库集合中查找黑暗契约
（Dark Pact）并放置入你的弃牌堆。

简化说明：
- "受到2点伤害和2点恐惧"按现有弱点惯例直接计入调查员（卡牌实现无
  DamageEngine 分配窗口通道，同 stars_of_hyades_lv0）。
- 毁灭标记放置后立即经 MythosPhase._check_doom_threshold 检查推进
  （同 dark_memory）。
- "从牌组中移除"记入 scenario.vars["removed_from_game"]（引擎无独立移除区，
  与 abandoned_and_alone 同一惯例）。
- "从牌库集合查找黑暗契约"实现为将 dark_pact_lv0 加入弃牌堆（collection
  是战役级概念，此处直接生成该卡）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class ThePriceOfFailure(CardImplementation):
    card_id = "the_price_of_failure_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._bus = None

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus  # 毁灭阈值检查需要经事件总线通知密谋推进

    @on_event(GameEvent.CARD_DRAWN, priority=TimingPriority.WHEN)
    def revelation(self, ctx):
        if ctx.extra.get("card_id") != "the_price_of_failure_lv0":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if "the_price_of_failure_lv0" in inv.hand:
            inv.hand.remove("the_price_of_failure_lv0")

        # 2点伤害和2点恐惧（直接计入，省略分配窗口）
        inv.damage += 2
        inv.horror += 2

        # 在当前密谋上放置1个毁灭标记并立即检查推进
        ctx.game_state.scenario.doom_on_agenda += 1
        if self._bus is not None:
            from backend.engine.phase_mythos import MythosPhase
            MythosPhase(ctx.game_state, self._bus)._check_doom_threshold()

        # 从牌组中移除（移出游戏）
        ctx.game_state.scenario.vars.setdefault(
            "removed_from_game", []).append("the_price_of_failure_lv0")

        # 从牌库集合查找黑暗契约，放置入弃牌堆
        inv.discard.append("dark_pact_lv0")

        ctx.game_state.log_effect(
            "🩸 失败的代价：受到2点伤害和2点恐惧，密谋+1毁灭，"
            "【黑暗契约】加入弃牌堆"
        )
        ctx.extra["price_of_failure_resolved"] = True
