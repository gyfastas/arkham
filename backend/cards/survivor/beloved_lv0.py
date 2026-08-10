"""Beloved (Level 0) — Survivor Skill.
若本次检定中揭示了[祝福]标记，你可以将挚爱移出游戏，将该标记的效果替换为：
"你自动成功。（不要再额外揭示标记。本次检定结束后将该标记返回混乱袋。）"

简化说明：
- 自动触发（官方为"可以"选择）：本卡投入后揭示祝福标记时自动生效。
- 自动成功：SKILL_TEST_FAILED 时翻转 ctx.success（同 lucky 机制）；
  引擎祝福标记本就只提供+2修正、无额外揭示（引擎缺口），替换效果中的
  "不再揭示"无实际差异。
- "检定结束后返回混乱袋"：引擎抽取标记不从袋中移除，无需返回（记注）。
- 移出游戏：ST.8 投入的卡进弃牌堆后，本卡在 SKILL_TEST_ENDS 从弃牌堆
  移至 scenario.vars["removed_from_game"]（引擎无独立移除区，沿用既有约定）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import ChaosTokenType, GameEvent, TimingPriority


class Beloved(CardImplementation):
    card_id = "beloved_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._armed_for: str | None = None

    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.WHEN)
    def replace_bless_effect(self, ctx):
        # 本实现仅在投入本次检定时被临时激活（技能卡无在场形态）
        if ctx.chaos_token != ChaosTokenType.BLESS:
            return
        self._armed_for = ctx.investigator_id
        ctx.extra["beloved_auto_success"] = True
        ctx.game_state.log_effect(
            "💝 挚爱：祝福标记效果替换为自动成功，本卡将移出游戏")

    @on_event(GameEvent.SKILL_TEST_FAILED, priority=TimingPriority.WHEN)
    def auto_success(self, ctx):
        if self._armed_for != ctx.investigator_id:
            return
        ctx.success = True
        # 该事件的 extra 会进入检定结果（供 UI/测试观察）
        ctx.extra["beloved_auto_success"] = True

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def remove_from_game(self, ctx):
        try:
            if self._armed_for != ctx.investigator_id:
                return
            inv = ctx.game_state.get_investigator(ctx.investigator_id)
            if inv is not None and self.card_id in inv.discard:
                inv.discard.remove(self.card_id)
                ctx.game_state.scenario.vars.setdefault(
                    "removed_from_game", []).append(self.card_id)
        finally:
            self._armed_for = None
