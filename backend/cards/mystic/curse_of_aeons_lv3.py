"""Curse of Aeons (Level 3) — Mystic Asset. (07195)
[reaction]在你所在地点的单次技能检定中揭示第二个[curse]标记时，消耗万古诅咒：
取消该标记，并改为将其视为如同[skull]标记。在检定结束后，你可以选择将这
两个标记都从混乱袋移除。

简化说明：
- 按 CHAOS_TOKEN_RESOLVED 统计单次检定中揭示的[curse]数（SKILL_TEST_BEGINS
  重置）；第二个[curse]时若本卡就绪则消耗：取消该标记并视为[skull]
  （引擎中[skull]修正为场景相关、按0结算，等效移除-2修正）。
- "检定结束后可选择移除两个[curse]"：自动选择移除（经 bind_chaos_bag 注入
  游戏袋；未注入或未揭示足够[curse]时跳过）。
- 引擎一次检定通常只揭示1个标记（无祝福/诅咒连抽机制——引擎缺口），
  多标记场景由测试/会话层逐枚发事件。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import ChaosTokenType, GameEvent, TimingPriority


class CurseOfAeons(CardImplementation):
    card_id = "curse_of_aeons_lv3"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._chaos_bag = None
        self._curse_count = 0
        self._triggered = False

    def bind_chaos_bag(self, chaos_bag) -> None:
        """注入游戏混沌袋（registry.activate_card 自动调用）。"""
        self._chaos_bag = chaos_bag

    def _holder_at_test_location(self, ctx):
        """本卡持有者与检定者同地点时返回持有者。"""
        tester = ctx.game_state.get_investigator(ctx.investigator_id)
        if tester is None:
            return None
        for inv in ctx.game_state.investigators.values():
            if self.instance_id in inv.play_area \
                    and inv.location_id == tester.location_id:
                return inv
        return None

    @on_event(GameEvent.SKILL_TEST_BEGINS, priority=TimingPriority.AFTER)
    def reset_count(self, ctx):
        self._curse_count = 0
        self._triggered = False

    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.REACTION)
    def cancel_second_curse(self, ctx):
        """同次检定第二个[curse]：消耗本卡，取消并视为[skull]。"""
        if ctx.chaos_token != ChaosTokenType.CURSE or self._triggered:
            return
        if self._holder_at_test_location(ctx) is None:
            return
        self._curse_count += 1
        if self._curse_count < 2:
            return
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is None or inst.exhausted:
            return
        inst.exhausted = True
        self._triggered = True

        # 取消[curse]并视为[skull]（[skull]修正场景相关，引擎按0结算）
        if ctx.amount:
            ctx.modify_amount(-ctx.amount, "curse_of_aeons_cancel")
        ctx.chaos_token = ChaosTokenType.SKULL
        ctx.extra["curse_of_aeons_triggered"] = True
        ctx.game_state.log_effect("☠️ 万古诅咒：第二个[curse]被取消并视为[skull]")

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def remove_curses_after_test(self, ctx):
        """检定结束：自动将两个[curse]移出混乱袋。"""
        if self._triggered and self._chaos_bag is not None:
            removed = 0
            for _ in range(2):
                if self._chaos_bag.remove(ChaosTokenType.CURSE):
                    removed += 1
            if removed:
                ctx.extra["curse_of_aeons_removed"] = removed
                ctx.game_state.log_effect(
                    f"☠️ 万古诅咒：从混乱袋移除{removed}个[curse]")
        self._curse_count = 0
        self._triggered = False
