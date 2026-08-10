"""Jacob Morrison (Level 3) — Survivor Asset, Ally slot. (07309)
Jacob Morrison does not ready during the upkeep phase.
[reaction] When you would fail a skill test, exhaust Jacob Morrison:
You get +2 skill value for that test.
[reaction] After a [bless] token is revealed from the chaos bag during a
skill test you are performing: Ready Jacob Morrison.

简化说明：
- "不在 upkeep 准备"：引擎刷新流程先就绪再发 CARD_READIED，无法阻止；
  近似为 CARD_READIED 时重新横置（同 wracked_by_nightmares 模式）。
- "+2技能值"：仅在差值≤2、足以翻转失败时自动横置（避免无意义消耗；
  官方由玩家选择）。翻转机制同 lucky。
- 祝福准备由本实现直接置 ready（不发 CARD_READIED 事件），不会触发
  上述重横置。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import ChaosTokenType, GameEvent, TimingPriority


class JacobMorrison(CardImplementation):
    card_id = "jacob_morrison_lv3"

    def _ready_instance(self, ctx):
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return None, None
        inst = ctx.game_state.get_card_instance(self.instance_id)
        return inv, inst

    @on_event(GameEvent.CARD_READIED, priority=TimingPriority.AFTER)
    def no_upkeep_ready(self, ctx):
        """ upkeep 中不准备：被引擎就绪后立即重新横置。"""
        if ctx.target != self.instance_id:
            return
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is not None:
            inst.exhausted = True

    @on_event(GameEvent.SKILL_TEST_FAILED, priority=TimingPriority.WHEN)
    def exhaust_for_bonus(self, ctx):
        """你即将检定失败时：横置雅各布，本次检定 +2 技能值。"""
        inv, inst = self._ready_instance(ctx)
        if inst is None or inst.exhausted:
            return
        margin = (ctx.difficulty or 0) - (ctx.modified_skill or 0)
        if margin > 2:
            return  # +2 不足以翻转，不浪费横置（简化）
        inst.exhausted = True
        ctx.success = True
        ctx.extra["jacob_morrison_turned_success"] = True
        ctx.game_state.log_effect(
            "⛪ 雅各布·莫里森：横置，+2技能值，检定失败转为成功")

    @on_event(GameEvent.CHAOS_TOKEN_REVEALED, priority=TimingPriority.AFTER)
    def ready_on_bless(self, ctx):
        """你进行检定揭示祝福标记后：准备雅各布。"""
        if ctx.chaos_token != ChaosTokenType.BLESS:
            return
        inv, inst = self._ready_instance(ctx)
        if inst is not None and inst.exhausted:
            inst.exhausted = False
            ctx.game_state.log_effect("⛪ 雅各布·莫里森：揭示祝福标记，准备")
