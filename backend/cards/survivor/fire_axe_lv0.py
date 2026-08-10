"""Fire Axe (Level 0) — Survivor Asset, Hand slot.
[action]: Fight. If you have no resources in your resource pool, this attack
deals +1 damage.
[fast] During an attack using Fire Axe, spend 1 resource: You get +2 [combat]
for this skill test. (Limit three times per attack.)

简化说明：
- 花费能力沿用 ResourceSkillBoost 的"先支付武装、下次对应技能检定生效"模式，
  但仅在使用消防斧的攻击（ctx.source 为斧）时生效；每次攻击限3次。
"""

from backend.cards._shared import ResourceSkillBoost
from backend.cards.base import on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class FireAxe(ResourceSkillBoost):
    card_id = "fire_axe_lv0"
    boosted_skills = (Skill.COMBAT,)
    spend_limit_per_attack = 3
    combat_per_spend = 2

    def spend(self, game_state, investigator_id: str, skill: Skill) -> bool:
        """花费1资源：本次攻击 +2 战斗（每次攻击限3次，可叠加）。"""
        if sum(self._armed.values()) >= self.spend_limit_per_attack:
            return False
        return super().spend(game_state, investigator_id, skill)

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def apply_boost(self, ctx):
        """仅在使用消防斧的攻击中生效，每次支付 +2 战斗。"""
        count = self._armed.get(ctx.skill_type, 0)
        if not count:
            return
        if ctx.source != self.instance_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        ctx.modify_amount(self.combat_per_spend * count, "fire_axe_boost")
        self._armed.pop(ctx.skill_type, None)

    @on_event(GameEvent.DAMAGE_DEALT, priority=TimingPriority.WHEN)
    def zero_resource_damage(self, ctx):
        """资源池为0时，本次攻击造成+1伤害。"""
        if ctx.source != self.instance_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is not None and inv.resources == 0:
            ctx.modify_amount(1, "fire_axe_zero_resource_damage")
