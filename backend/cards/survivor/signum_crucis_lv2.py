"""Signum Crucis (Level 2) — Survivor Skill. (07197)
只能在你执行的技能检定中投入，且该检定难度必须高于你的基础技能值。
在你投入十字圣号到技能检定后，加入X个 [bless] 标记到混乱袋。X为本检定难度
和你的基础技能值之差。

简化说明：
- "仅你执行的检定、且难度高于基础技能值"为投入合法性限制，由会话层投入
  窗口约束；本实现只在 X>0 时加标记（X≤0 时效果为空，与官方一致）。
- 基础技能值取调查员卡面印刷值（不含在场资产加值）。
- 混沌袋经 bind_chaos_bag 注入（registry 在投入激活/会话层接线；未绑定时
  效果不触发）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import ChaosTokenType, GameEvent, TimingPriority


class SignumCrucis(CardImplementation):
    card_id = "signum_crucis_lv2"

    def bind_chaos_bag(self, chaos_bag) -> None:
        """注入混沌袋（registry.activate_card / 测试接线）。"""
        self._chaos_bag = chaos_bag

    @on_event(GameEvent.SKILL_TEST_COMMIT, priority=TimingPriority.AFTER)
    def add_bless_tokens(self, ctx):
        """投入后：加入 X 个祝福标记，X = 难度 - 基础技能值。"""
        if self.card_id not in (ctx.committed_cards or []):
            return
        bag = getattr(self, "_chaos_bag", None)
        if bag is None:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or ctx.skill_type is None:
            return
        base = inv.get_skill(ctx.skill_type)
        x = (ctx.difficulty or 0) - base
        if x <= 0:
            return
        for _ in range(x):
            bag.add_token(ChaosTokenType.BLESS)
        ctx.extra["signum_crucis_bless"] = x
        ctx.game_state.log_effect(f"✝ 十字圣号：加入{x}个祝福标记到混乱袋")
