"""Take the Initiative (Level 0) — Guardian Skill. (04150)
印刷图标：3个[wild]。只能在你执行的技能检定中投入。
任何调查员在本阶段每完成1个行动，占据先机失去[wild]。

简化说明：
- "只能在你执行的检定中投入"由会话层校验（引擎提交通道不验证）。
- 本阶段已完成行动数记录在 scenario.vars（提交时引擎会为投入卡新建临时
  实例，实例状态不可用，故用场景级计数）：手牌中的持续注册实例监听
  ACTION_PERFORMED 累加、各阶段开始事件清零。
- 提交时持久实例与临时实例都会收到 SKILL_TEST_COMMIT，经 ctx.extra 去重，
  图标只扣减一次。
- 已知边缘情况：两位调查员手牌各持一张时行动计数会翻倍（官方共享同一
  阶段计数，本应只计一次），注明。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority

_VAR = "take_the_initiative_actions"
_MAX_ICONS = 3


class TakeTheInitiative(CardImplementation):
    card_id = "take_the_initiative_lv0"
    persistent_in_hand = True  # 手牌中持续跟踪本阶段行动数

    @on_event(GameEvent.MYTHOS_PHASE_BEGINS, priority=TimingPriority.AFTER)
    @on_event(GameEvent.INVESTIGATION_PHASE_BEGINS, priority=TimingPriority.AFTER)
    @on_event(GameEvent.ENEMY_PHASE_BEGINS, priority=TimingPriority.AFTER)
    @on_event(GameEvent.UPKEEP_PHASE_BEGINS, priority=TimingPriority.AFTER)
    def reset_phase(self, ctx):
        ctx.game_state.scenario.vars[_VAR] = 0

    @on_event(GameEvent.ACTION_PERFORMED, priority=TimingPriority.AFTER)
    def count_action(self, ctx):
        vars_ = ctx.game_state.scenario.vars
        vars_[_VAR] = vars_.get(_VAR, 0) + 1

    @on_event(GameEvent.SKILL_TEST_COMMIT, priority=TimingPriority.WHEN)
    def lose_icons(self, ctx):
        """本阶段每已完成1个行动：失去1个通用图标（至多失去3个）。"""
        if self.card_id not in (ctx.committed_cards or []):
            return
        if ctx.extra.get("take_the_initiative_applied"):
            return  # 持久实例与临时实例去重
        ctx.extra["take_the_initiative_applied"] = True
        actions = ctx.game_state.scenario.vars.get(_VAR, 0)
        penalty = min(_MAX_ICONS, actions)
        if penalty:
            ctx.modify_amount(-penalty, "take_the_initiative_decay")
