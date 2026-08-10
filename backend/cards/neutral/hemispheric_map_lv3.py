"""Hemispheric Map (Level 3) — Neutral Asset, Accessory slot.
当你当前地点连接至少2个其他地点时，你获得+1[willpower]和+1[intellect]。
当你当前地点连接至少4个其他地点时，你额外获得+1[willpower]和+1[intellect]。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class HemisphericMap(CardImplementation):
    card_id = "hemispheric_map_lv3"

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def skill_bonus(self, ctx):
        if ctx.skill_type not in (Skill.WILLPOWER, Skill.INTELLECT):
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        location = ctx.game_state.get_location(inv.location_id)
        if location is None:
            return
        connections = len(location.connections)
        bonus = 0
        if connections >= 2:
            bonus += 1
        if connections >= 4:
            bonus += 1
        if bonus:
            ctx.modify_amount(bonus, "hemispheric_map_bonus")
