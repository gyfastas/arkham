"""Brute Force (Level 1) — Survivor Skill.
每次技能检定最多投入1张。
只要在基础攻击行动中投入蛮力，其获得[战斗][战斗]和以下文本：
"若本次检定成功且超过难度至少2点，本次攻击造成+2伤害。"

简化说明：
- 投入的卡实现仅在检定流程内临时激活，无法区分"基础攻击行动"与其他
  战斗检定（同 survival_instinct 的既有简化）：任何投入了本卡的战斗检定
  均生效。
- "最多投入1张"为投入限制：引擎无投入校验钩子（引擎缺口，同
  not_without_a_fight 记注）。
- +2伤害经 ctx.extra["bonus_damage"] 通道汇入战斗结算（vicious_blow 同通道）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class BruteForce(CardImplementation):
    card_id = "brute_force_lv1"

    @on_event(GameEvent.SKILL_TEST_COMMIT, priority=TimingPriority.WHEN)
    def bonus_icons(self, ctx):
        """基础攻击中投入：额外[战斗][战斗]（对战斗检定+2）。"""
        if self.card_id not in ctx.committed_cards:
            return
        if ctx.skill_type != Skill.COMBAT:
            return
        ctx.modify_amount(2, "brute_force_icons")

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.WHEN)
    def bonus_damage(self, ctx):
        """成功且超出难度≥2：本次攻击+2伤害。"""
        if self.card_id not in ctx.committed_cards:
            return
        if ctx.skill_type != Skill.COMBAT:
            return
        margin = (ctx.modified_skill or 0) - (ctx.difficulty or 0)
        if margin < 2:
            return
        ctx.extra["bonus_damage"] = int(ctx.extra.get("bonus_damage", 0) or 0) + 2
        ctx.game_state.log_effect("👊 蛮力：超出难度2点，本次攻击+2伤害")
