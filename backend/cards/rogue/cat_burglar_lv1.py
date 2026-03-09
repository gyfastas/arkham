"""Cat Burglar (Level 1) — Rogue Asset.
飞贼。+1敏捷。消耗：脱离一个敌人并移动到相连地点。
"""
from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class CatBurglar(CardImplementation):
    card_id = "cat_burglar_lv1"

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def agility_bonus(self, ctx):
        """Provide +1 agility while in play."""
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv and self.instance_id in inv.play_area:
            if ctx.extra.get("skill_type") == Skill.AGILITY:
                ctx.extra["skill_value"] = ctx.extra.get("skill_value", 0) + 1
