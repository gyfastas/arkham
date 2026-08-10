"""Trial by Fire (Level 0) — Survivor Event. (05281)
快速。只能在你回合中打出。
选择你的一项技能。直到你的回合结束，将该技能的基础值设为5。

简化说明：
- "只能在你回合中打出"由会话层打出窗口约束。
- "选择一项技能"可经 ctx.extra["skill"]（"willpower"/"intellect"/"combat"/
  "agility"）指定；未指定时自动选择基础值最低的一项（官方为玩家自选）。
- "基础值设为5"经 SKILL_VALUE_DETERMINED 修正实现：按 (5 - 基础值) 加减，
  投入图标/标记/其他加值照常叠加；若基础值高于5同样会被降到5（官方如此，
  自动选择最低技能时不会出现）。
- 事件实现实例存活到 ROUND_ENDS，回合结束（INVESTIGATOR_TURN_ENDS）即失效。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority

_SKILLS = (Skill.WILLPOWER, Skill.INTELLECT, Skill.COMBAT, Skill.AGILITY)


class TrialByFire(CardImplementation):
    card_id = "trial_by_fire_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._owner: str | None = None
        self._skill: Skill | None = None

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def choose_skill(self, ctx):
        """打出时：选定技能（extra 指定或自动选基础值最低者）。"""
        if ctx.extra.get("card_id") != self.card_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        skill = None
        requested = ctx.extra.get("skill")
        if requested:
            for s in _SKILLS:
                if s.value == requested:
                    skill = s
                    break
        if skill is None:
            skill = min(_SKILLS, key=lambda s: inv.get_skill(s))
        self._owner = inv.investigator_id
        self._skill = skill
        ctx.extra["trial_by_fire_skill"] = skill.value
        ctx.game_state.log_effect(
            f"🔥 勇闯火线：本回合 {skill.value} 基础值设为5")

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def set_base_value(self, ctx):
        """将选定技能的基础值设为5（按差值修正最终值）。"""
        if self._skill is None or ctx.skill_type != self._skill:
            return
        if ctx.investigator_id != self._owner:
            return
        base = ctx.extra.get("base_skill")
        if base is None:
            inv = ctx.game_state.get_investigator(ctx.investigator_id)
            if inv is None:
                return
            base = inv.get_skill(ctx.skill_type)
        delta = 5 - base
        if delta:
            ctx.modify_amount(delta, "trial_by_fire_base_5")

    @on_event(GameEvent.INVESTIGATOR_TURN_ENDS, priority=TimingPriority.AFTER)
    def clear_at_turn_end(self, ctx):
        """回合结束：效果失效。"""
        if ctx.investigator_id == self._owner:
            self._owner = None
            self._skill = None
