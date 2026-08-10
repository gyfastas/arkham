"""Defensive Stance (Level 1) — Guardian Skill. (05157)
当防御姿态在你的手牌中或被投入到技能检定时，它获得等同于你敏捷的
[combat]图标，以及等同于你战斗的[agility]图标。

简化说明：
- 动态图标经 SKILL_TEST_COMMIT 汇入投入图标总数：战斗检定加你的敏捷值、
  敏捷检定加你的战斗值，其余技能检定无图标（牌面数据 skill_icons 为空）。
- "在手牌中"仅影响手牌参考展示；引擎中手牌图标只在投入时生效，无差异。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class DefensiveStance(CardImplementation):
    card_id = "defensive_stance_lv1"

    @on_event(GameEvent.SKILL_TEST_COMMIT, priority=TimingPriority.WHEN)
    def dynamic_icons(self, ctx):
        """投入时：战斗检定+敏捷值图标，敏捷检定+战斗值图标。"""
        if self.card_id not in ctx.committed_cards:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if ctx.skill_type == Skill.COMBAT:
            amount = inv.get_skill(Skill.AGILITY)
        elif ctx.skill_type == Skill.AGILITY:
            amount = inv.get_skill(Skill.COMBAT)
        else:
            return
        if amount <= 0:
            return
        ctx.modify_amount(amount, "defensive_stance_icons")
        ctx.extra["defensive_stance_icons"] = amount
        ctx.game_state.log_effect(f"🛡️ 防御姿态：本次检定+{amount}图标")
