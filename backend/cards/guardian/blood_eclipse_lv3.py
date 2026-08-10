"""Blood Eclipse (Level 3) — Guardian Event. (04266)
作为打出鲜血失色的额外费用，受到至多3点伤害。
攻击。本次攻击使用意志代替战斗。每有1点作为本卡费用受到的伤害，
本次攻击你获得+1意志并造成+1伤害。

简化说明：
- 额外费用"至多3点伤害"简化为自动受到不致败的最大量（至多3点，
  保留至少1点剩余生命）；可通过 ctx.extra["blood_eclipse_damage"] 指定
  （会话层打出时注入）。
- 打出后由会话层发起战斗行动（同 backstab 惯例）；本实现武装持有者
  下一次战斗检定：以意志代替战斗 + 每点费用伤害 +1意志/+1伤害。
- 事件实现实例存活至 ROUND_ENDS（引擎事件生命周期），武装仅限一次检定。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority

_MAX_COST_DAMAGE = 3


class BloodEclipse(CardImplementation):
    card_id = "blood_eclipse_lv3"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._armed_for = None  # investigator_id
        self._power = 0         # 作为费用受到的伤害数

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def arm(self, ctx):
        """打出时：受到至多3点伤害作为额外费用，武装一次强化攻击。"""
        if ctx.extra.get("card_id") != self.card_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        # 自动受到不致败的最大伤害（至多3点，保留至少1点剩余生命）
        safe = max(0, inv.health - inv.damage - 1)
        amount = ctx.extra.get("blood_eclipse_damage")
        amount = int(amount) if amount is not None else _MAX_COST_DAMAGE
        amount = max(0, min(amount, _MAX_COST_DAMAGE, safe))
        inv.damage += amount
        self._armed_for = inv.investigator_id
        self._power = amount
        ctx.extra["blood_eclipse_power"] = amount
        ctx.game_state.log_effect(
            f"🩸 鲜血失色：作为额外费用受到{amount}点伤害，攻击+{amount}意志/+{amount}伤害")

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def substitute_and_boost(self, ctx):
        """武装的攻击：以意志代替战斗，每点费用伤害+1意志。"""
        if ctx.skill_type != Skill.COMBAT:
            return
        if self._armed_for is None or ctx.investigator_id != self._armed_for:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        base_val = inv.get_skill(ctx.skill_type)
        willpower = inv.get_skill(Skill.WILLPOWER)
        ctx.modify_amount(
            willpower - base_val + self._power, "blood_eclipse_substitute")

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.WHEN)
    def bonus_damage(self, ctx):
        """武装的攻击成功：每点费用伤害+1伤害。"""
        if ctx.skill_type != Skill.COMBAT:
            return
        if self._armed_for is None or ctx.investigator_id != self._armed_for:
            return
        if self._power > 0:
            ctx.extra["bonus_damage"] = int(
                ctx.extra.get("bonus_damage", 0) or 0) + self._power

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        self._armed_for = None
        self._power = 0
