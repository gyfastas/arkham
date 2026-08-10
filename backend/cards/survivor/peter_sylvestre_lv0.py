"""Peter Sylvestre (Level 0) — Survivor Asset, Ally slot.
You get +1 [agility].
[reaction] After your turn ends: Heal 1 horror from Peter Sylvestre.
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class PeterSylvestre(CardImplementation):
    card_id = "peter_sylvestre_lv0"

    @on_event(
        GameEvent.SKILL_VALUE_DETERMINED,
        priority=TimingPriority.WHEN,
    )
    def agility_bonus(self, ctx):
        """+1 Agility while Peter Sylvestre is in play."""
        if ctx.skill_type != Skill.AGILITY:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv and self.instance_id in inv.play_area:
            ctx.modify_amount(1, "peter_sylvestre_agility")

    @on_event(GameEvent.INVESTIGATOR_TURN_ENDS, priority=TimingPriority.AFTER)
    def heal_horror(self, ctx):
        """你的回合结束后：治愈彼得·希尔维斯特1点恐惧。"""
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is not None and inst.horror > 0:
            inst.horror -= 1
