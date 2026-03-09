"""Vicious Blow (Level 0) — Guardian Skill.
提交到战斗检定。如果攻击成功，+1伤害。
"""
from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class ViciousBlow(CardImplementation):
    card_id = "vicious_blow_lv0"

    @on_event(
        GameEvent.SKILL_TEST_SUCCESSFUL,
        priority=TimingPriority.AFTER,
    )
    def extra_damage(self, ctx):
        """If combat test is successful with Vicious Blow committed, +1 damage."""
        if "vicious_blow_lv0" not in getattr(ctx, 'committed_cards', []):
            return
        if ctx.skill_type != Skill.COMBAT:
            return
        ctx.extra["bonus_damage"] = ctx.extra.get("bonus_damage", 0) + 1
