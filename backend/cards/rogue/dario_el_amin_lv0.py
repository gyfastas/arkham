"""Dario El-Amin (Level 0) — Rogue Asset, Ally slot.
如果你有10点或以上资源，你获得+1意志和+1智力。
[行动]如果你所在地点没有敌人，消耗达里奥·埃尔阿明：获得2资源。

简化说明：
- "你所在地点没有敌人"包括未交战（地点敌人列表）与已交战
  （你的威胁区域）的敌人。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class DarioElAmin(CardImplementation):
    card_id = "dario_el_amin_lv0"
    activations = [{
        "id": "gain",
        "label": "消耗：获得2资源（需地点无敌人）",
        "method": "activate",
        "actions": 1,
    }]

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def skill_bonus(self, ctx):
        """持有10+资源时：+1意志、+1智力。"""
        if ctx.skill_type not in (Skill.WILLPOWER, Skill.INTELLECT):
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        if inv.resources >= 10:
            ctx.modify_amount(1, "dario_el_amin_bonus")

    def activate(self, game_state, investigator_id: str) -> bool:
        """[行动]地点无敌人时，消耗：获得2资源。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None or inst.exhausted:
            return False
        loc = game_state.get_location(inv.location_id)
        if loc is not None and loc.enemies:
            return False
        if inv.threat_area:
            return False
        inst.exhausted = True
        inv.resources += 2
        return True
