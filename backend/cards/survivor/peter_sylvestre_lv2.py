"""Peter Sylvestre (Level 2) — Survivor Asset, Ally slot.
你获得+1[agility]和+1[willpower]。
[reaction]在你回合结束后：治愈彼得·希尔维斯特1点恐惧。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class PeterSylvestreLv2(CardImplementation):
    card_id = "peter_sylvestre_lv2"

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def skill_bonus(self, ctx):
        """+1敏捷、+1意志。"""
        if ctx.skill_type not in (Skill.AGILITY, Skill.WILLPOWER):
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv and self.instance_id in inv.play_area:
            ctx.modify_amount(1, "peter_sylvestre_lv2_bonus")

    @on_event(GameEvent.INVESTIGATOR_TURN_ENDS, priority=TimingPriority.AFTER)
    def heal_horror(self, ctx):
        """你的回合结束后：治愈彼得·希尔维斯特1点恐惧。"""
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is not None and inst.horror > 0:
            inst.horror -= 1
