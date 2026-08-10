"""Police Badge (Level 2) — Guardian Asset, Accessory slot.
你获得+1意志。
[快速]当你所在地点的一位调查员正在其回合中时，弃置警徽：
该调查员本回合可额外执行2个行动。

简化说明：
- "正在其回合中"的窗口校验由会话层负责；激活方法默认可随时调用。
- 通用激活通道只传使用者，默认给使用者+2行动；可传
  target_investigator_id 指定同地点的其他调查员。
"""
from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class PoliceBadge(CardImplementation):
    card_id = "police_badge_lv2"
    activations = [{
        "id": "discard_actions",
        "label": "弃置警徽：该调查员+2行动",
        "method": "activate_discard_actions",
        "actions": 0,
        "resource_cost": 0,
    }]

    def activate_discard_actions(self, game_state, investigator_id: str,
                                 target_investigator_id: str | None = None) -> bool:
        """弃置警徽：同地点的目标调查员（默认自己）本回合+2行动。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        target = game_state.get_investigator(target_investigator_id or investigator_id)
        if target is None or target.location_id != inv.location_id:
            return False

        manager = getattr(game_state, "slot_managers", {}).get(investigator_id)
        if manager:
            manager.vacate(self.instance_id)
        inv.play_area.remove(self.instance_id)
        inv.discard.append(self.card_id)
        game_state.cards_in_play.pop(self.instance_id, None)
        target.actions_remaining += 2
        return True

    @on_event(
        GameEvent.SKILL_VALUE_DETERMINED,
        priority=TimingPriority.WHEN,
    )
    def willpower_bonus(self, ctx):
        """+1 Willpower while Police Badge is in play."""
        if ctx.skill_type == Skill.WILLPOWER:
            inv = ctx.game_state.get_investigator(ctx.investigator_id)
            if inv and self.instance_id in inv.play_area:
                ctx.modify_amount(1, "police_badge_willpower_bonus")
