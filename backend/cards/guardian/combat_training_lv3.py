"""Combat Training (Level 3) — Guardian Asset. (08027)
快速。场上限制1张[[Composure]]。生命3、理智1。
你获得+1战斗和+1敏捷。
非直接伤害/恐惧必须先分配给战斗训练，然后才能分配给你的调查员卡。
[快速]花费1资源：本次技能检定你获得+1战斗或+1敏捷。

简化说明：
- 花费泵沿用 ResourceSkillBoost（战斗/敏捷，可叠加，见 _shared.py）。
- 被动 +1战斗/+1敏捷：SKILL_VALUE_DETERMINED 时在场即生效。
- "伤害/恐惧必须先分配给本卡"简化为自动承伤承恐：对持有者的非直接
  伤害/恐惧，自动将至多本卡剩余生命/理智的量改由本卡承担
  （官方为分配顺序规则；直接伤害/恐惧不经分配事件，天然豁免）。
- 本卡承伤/承恐达到上限即被击败离场（镜像引擎离场流程）。
- "限制1张Composure"为同名牌限制规则，引擎无同名限制通道，未强制（同 lv1 注明）。
"""

from backend.cards._shared import ResourceSkillBoost, defeat_asset
from backend.cards.base import on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class CombatTrainingLv3(ResourceSkillBoost):
    card_id = "combat_training_lv3"
    boosted_skills = (Skill.COMBAT, Skill.AGILITY)

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._bus = None

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def passive_bonus(self, ctx):
        """在场时 +1 战斗、+1 敏捷。"""
        if ctx.skill_type not in (Skill.COMBAT, Skill.AGILITY):
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is not None and self.instance_id in inv.play_area:
            ctx.modify_amount(1, "combat_training_lv3_passive")

    def _soak(self, ctx, attr: str, capacity_attr: str, reason: str) -> None:
        """非直接伤害/恐惧优先由本卡承担（至多本卡剩余上限）。"""
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inv is None or inst is None or self.instance_id not in inv.play_area:
            return
        data = ctx.game_state.get_card_data(inst.card_id)
        capacity = getattr(data, capacity_attr, None) if data else None
        if capacity is None:
            return
        remaining = capacity - getattr(inst, attr)
        amount = min(remaining, ctx.amount or 0)
        if amount <= 0:
            return
        setattr(inst, attr, getattr(inst, attr) + amount)
        ctx.modify_amount(-amount, reason)
        ctx.game_state.log_effect(f"🥋 战斗训练(3)：代为承担{amount}点")
        if getattr(inst, attr) >= capacity:
            defeat_asset(ctx.game_state, self._bus, self.instance_id)
            ctx.game_state.log_effect("🥋 战斗训练(3)：达到上限，被击败")

    @on_event(GameEvent.DAMAGE_ASSIGNED, priority=TimingPriority.WHEN)
    def soak_damage(self, ctx):
        self._soak(ctx, "damage", "health", "combat_training_lv3_soak_damage")

    @on_event(GameEvent.HORROR_ASSIGNED, priority=TimingPriority.WHEN)
    def soak_horror(self, ctx):
        self._soak(ctx, "horror", "sanity", "combat_training_lv3_soak_horror")
