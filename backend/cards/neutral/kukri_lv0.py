"""Kukri (Level 0) — Neutral Asset, Hand slot.
[action]：攻击。这次攻击中你+1[combat]。如果成功，你可以花费1额外行动，
来使这次攻击造成+1伤害。

简化说明：
- "花费1额外行动换+1伤害"实现为 activate_bonus_damage() 公开方法，
  由会话层在攻击成功后、玩家确认支付额外行动时调用。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class Kukri(CardImplementation):
    card_id = "kukri_lv0"
    activations = [{"id": "bonus_damage", "label": "攻击成功后花1行动：+1伤害", "method": "activate_bonus_damage", "target": "enemy", "actions": 1, "timing": "combat"}]

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def combat_bonus(self, ctx):
        """用弯刀攻击时 +1 战斗。"""
        if ctx.skill_type != Skill.COMBAT:
            return
        if ctx.extra.get("weapon_card_id") != "kukri_lv0":
            return
        ctx.modify_amount(1, "kukri_combat_bonus")

    @staticmethod
    def activate_bonus_damage(game_state, investigator_id: str,
                              enemy_instance_id: str) -> bool:
        """攻击成功后花费1额外行动：对该敌人造成+1伤害。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return False
        if getattr(inv, "actions_remaining", 0) < 1:
            return False
        enemy = game_state.get_card_instance(enemy_instance_id)
        if enemy is None:
            return False
        inv.actions_remaining -= 1
        enemy.damage += 1
        return True
