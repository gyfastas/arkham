"""Blackjack (Level 0) — Guardian Asset, Hand slot.
[action]：攻击。这次攻击中你+1[combat]。如果你对与另一位调查员交战的敌人攻击
并且失败，则不会对调查员造成伤害。

简化说明：
- "误伤保护"依赖引擎的失手误伤流程（当前引擎未实现误伤），按设计天然安全，注明即可。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class Blackjack(CardImplementation):
    card_id = "blackjack_lv0"

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def combat_bonus(self, ctx):
        """用金属棍棒攻击时 +1 战斗（引擎以 ctx.source 传武器实例）。"""
        if ctx.skill_type != Skill.COMBAT:
            return
        if ctx.source != self.instance_id:
            return
        ctx.modify_amount(1, "blackjack_combat_bonus")
