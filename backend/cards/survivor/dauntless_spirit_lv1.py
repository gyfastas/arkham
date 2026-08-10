"""Dauntless Spirit (Level 1) — Survivor Skill.
只要无畏精神在你手中或被投入到技能检定中，其获得等同于你[战斗]的[意志]
图标，以及等同于你[意志]的[战斗]图标。

简化说明：
- 本卡无印刷图标；投入后按被检定技能结算动态图标：意志检定+等同于你战斗
  值的图标，战斗检定+等同于你意志值的图标（引擎只统计与检定技能匹配的
  图标，对智力/敏捷检定无贡献，与官方结算等价）。
- "在你手中"形态（供清点手牌图标类效果使用）引擎无对应通道（引擎缺口）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class DauntlessSpirit(CardImplementation):
    card_id = "dauntless_spirit_lv1"

    @on_event(GameEvent.SKILL_TEST_COMMIT, priority=TimingPriority.WHEN)
    def swapped_icons(self, ctx):
        """意志检定+战斗值图标；战斗检定+意志值图标。"""
        if self.card_id not in ctx.committed_cards:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        bonus = 0
        if ctx.skill_type == Skill.WILLPOWER:
            bonus = inv.get_skill(Skill.COMBAT)
        elif ctx.skill_type == Skill.COMBAT:
            bonus = inv.get_skill(Skill.WILLPOWER)
        if bonus <= 0:
            return
        ctx.modify_amount(bonus, "dauntless_spirit_swap")
        ctx.extra["dauntless_spirit_bonus"] = bonus
        ctx.game_state.log_effect(
            f"🦁 无畏精神：本次{ctx.skill_type.value}检定+{bonus}图标")
