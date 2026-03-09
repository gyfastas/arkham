"""Beat Cop (Level 2) — Guardian Asset, Ally slot.
+1战斗力。消耗并对其造成1点伤害：对一个敌人造成1点伤害。
"""
from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class BeatCopLv2(CardImplementation):
    card_id = "beat_cop_lv2"

    @on_event(
        GameEvent.SKILL_VALUE_DETERMINED,
        priority=TimingPriority.WHEN,
    )
    def combat_bonus(self, ctx):
        """+1 Combat while Beat Cop (2) is in play."""
        if ctx.skill_type == Skill.COMBAT:
            inv = ctx.game_state.get_investigator(ctx.investigator_id)
            if inv and self.instance_id in inv.play_area:
                ctx.modify_amount(1, "beat_cop_lv2_combat_bonus")
