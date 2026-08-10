"""Plan of Action (Level 0) — Seeker Skill. (07024)
如果这次技能检定在本回合的第一个行动中或之前，本卡获得[willpower][agility]。
如果这次技能检定在本回合的第一个和第三个行动之间且成功，抽1张牌。
如果这次技能检定在本回合的第三个行动中或之后，本卡获得[combat][intellect]。

简化说明：
- 回合进度以"已完成的行动数"判定（3 - actions_remaining；引擎在非快速行动
  结算后才扣减行动数，故检定发生时 actions_remaining 仍反映本行动之前的状态）：
  已完成0个 → 第一条款（+[willpower]+[agility]）；已完成1个 → 第二条款
  （成功抽1）；已完成≥2个 → 第三条款（+[combat]+[intellect]）。
  与官方的细微差异："第二与第三行动之间"的检定被归入第三条款（官方文字
  "between the first and third"或含此间隙），见报告。
- 获得的图标仅在与检定技能匹配时生效（引擎静态统计 wild 图标，条件图标
  由 SKILL_TEST_COMMIT 时按检定技能补加）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority

_CLAUSE1_ICONS = (Skill.WILLPOWER, Skill.AGILITY)
_CLAUSE3_ICONS = (Skill.COMBAT, Skill.INTELLECT)


class PlanOfAction(CardImplementation):
    card_id = "plan_of_action_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._clause: int = 0  # 本次检定局面的条款（提交时锁定）

    def _actions_done(self, ctx) -> int:
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return 0
        return max(0, 3 - inv.actions_remaining)

    @on_event(GameEvent.SKILL_TEST_COMMIT, priority=TimingPriority.WHEN)
    def conditional_icons(self, ctx):
        if self.card_id not in ctx.committed_cards:
            return
        done = self._actions_done(ctx)
        if done <= 0:
            self._clause = 1
            icons = _CLAUSE1_ICONS
        elif done == 1:
            self._clause = 2
            icons = ()
        else:
            self._clause = 3
            icons = _CLAUSE3_ICONS
        if ctx.skill_type in icons:
            ctx.modify_amount(1, "plan_of_action_icons")
            ctx.extra["plan_of_action_clause"] = self._clause

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.AFTER)
    def draw_on_middle_clause(self, ctx):
        """第二条款（第一与第三行动之间）成功：抽1张牌。"""
        if self.card_id not in ctx.committed_cards or self._clause != 2:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is not None and inv.deck:
            inv.hand.append(inv.deck.pop(0))
            ctx.extra["plan_of_action_drew"] = True
            ctx.game_state.log_effect("🗺️ 行动计划：检定成功，抽1张牌")

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        self._clause = 0
