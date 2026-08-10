"""Meat Cleaver (Level 0) — Survivor Asset, Hand slot. (05114)
[action]: Fight. You get +1 [combat] for this attack (+2 [combat] instead
if you have 3 or fewer remaining sanity). If this attack defeats an enemy,
you may heal 1 horror. As an additional cost to initiate this ability, you
may take 1 horror to have this attack deal +1 damage.

简化说明：
- "可承受1恐惧换+1伤害"为启动式附加费用（activations 声明，0行动）：
  调用 empower() 后下一次以菜刀发起的攻击 +1 伤害（经 DAMAGE_DEALT 通道，
  同 derringer）。
- "击败敌人可治愈1恐惧"自动结算（官方为 may，从简）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class MeatCleaver(CardImplementation):
    card_id = "meat_cleaver_lv0"
    activations = [{
        "id": "empower",
        "label": "承受1恐惧：本次菜刀攻击+1伤害",
        "method": "empower",
        "actions": 0,
    }]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._attack_active = False  # 本次攻击以菜刀发起
        self._empowered = False      # 已付1恐惧换+1伤害

    def empower(self, game_state, investigator_id: str) -> bool:
        """附加费用：承受1恐惧，下一次菜刀攻击 +1 伤害。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        if self._empowered:
            return False
        inv.horror += 1
        self._empowered = True
        game_state.log_effect("🔪 菜刀：承受1恐惧，本次攻击+1伤害")
        return True

    @on_event(GameEvent.FIGHT_ACTION_INITIATED, priority=TimingPriority.WHEN)
    def track_attack(self, ctx):
        if ctx.source == self.instance_id:
            self._attack_active = True

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def combat_bonus(self, ctx):
        """+1战斗；剩余理智≤3时改为+2。"""
        if ctx.source != self.instance_id or not self._attack_active:
            return
        if ctx.skill_type != Skill.COMBAT:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        bonus = 2 if inv.remaining_sanity <= 3 else 1
        ctx.modify_amount(bonus, "meat_cleaver_combat")

    @on_event(GameEvent.DAMAGE_DEALT, priority=TimingPriority.WHEN)
    def empowered_damage(self, ctx):
        """已付附加费用：本次攻击 +1 伤害。"""
        if ctx.source != self.instance_id or not self._empowered:
            return
        ctx.modify_amount(1, "meat_cleaver_empowered")

    @on_event(GameEvent.ENEMY_DEFEATED, priority=TimingPriority.AFTER)
    def heal_horror_on_defeat(self, ctx):
        """本次攻击击败敌人：治愈1点恐惧（may 自动结算）。"""
        if not self._attack_active:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        if inv.horror > 0:
            inv.horror -= 1
            ctx.game_state.log_effect("🔪 菜刀：击败敌人，治愈1点恐惧")

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        if ctx.source == self.instance_id:
            self._attack_active = False
            self._empowered = False
