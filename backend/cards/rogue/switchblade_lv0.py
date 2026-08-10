"""Switchblade (Level 0) — Rogue Asset, Hand slot.
快速。[行动]：攻击。若你成功且超出难度2点以上，本次攻击造成+1伤害。

简化说明：
- 武器攻击走标准武器流程（ctx.source 为本武器实例）；命中后无需扣弹药（无使用次数）。
- margin 伤害在 SKILL_TEST_SUCCESSFUL 检查 margin>=2，
  写入 ctx.extra["bonus_damage"] 由引擎结算。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class Switchblade(CardImplementation):
    card_id = "switchblade_lv0"

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.AFTER)
    def bonus_damage(self, ctx):
        """成功且超出难度2点以上：本次攻击造成+1伤害。"""
        if ctx.source != self.instance_id:
            return
        if ctx.skill_type != Skill.COMBAT:
            return
        margin = (ctx.modified_skill or 0) - (ctx.difficulty or 0)
        if margin < 2:
            return
        ctx.extra["bonus_damage"] = int(ctx.extra.get("bonus_damage", 0) or 0) + 1
