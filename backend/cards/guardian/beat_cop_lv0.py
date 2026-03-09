"""Beat Cop (Level 0) — Guardian Asset, Ally slot.
+1战斗力。弃置巡警：对你所在地点的一个敌人造成1点伤害。
"""
from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class BeatCop(CardImplementation):
    card_id = "beat_cop_lv0"

    @on_event(
        GameEvent.SKILL_VALUE_DETERMINED,
        priority=TimingPriority.WHEN,
    )
    def combat_bonus(self, ctx):
        """+1 Combat while Beat Cop is in play."""
        if ctx.skill_type == Skill.COMBAT:
            inv = ctx.game_state.get_investigator(ctx.investigator_id)
            if inv and self.instance_id in inv.play_area:
                ctx.modify_amount(1, "beat_cop_combat_bonus")
