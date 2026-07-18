"""Switchblade (Level 0) — Rogue Asset, Hand slot.
快速。消耗弹簧刀：攻击。你获得+1战斗，本次攻击造成+1伤害。

简化说明：
- 武器攻击走标准武器流程（weapon_card_id）；命中后无需扣弹药（无使用次数）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class Switchblade(CardImplementation):
    card_id = "switchblade_lv0"

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def combat_bonus(self, ctx):
        if ctx.skill_type != Skill.COMBAT:
            return
        if ctx.extra.get("weapon_card_id") != "switchblade_lv0":
            return
        ctx.modify_amount(1, "switchblade_combat_bonus")

    @on_event(GameEvent.DAMAGE_DEALT, priority=TimingPriority.WHEN)
    def bonus_damage(self, ctx):
        if ctx.source != self.instance_id:
            return
        ctx.modify_amount(1, "switchblade_bonus_damage")
