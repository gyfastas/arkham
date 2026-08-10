"""Gang Up (Level 1) — Guardian Event. (08022)
攻击。你控制的卡牌中每有一种不同的阵营，本次攻击你获得+1战斗并造成+1伤害。

简化说明：
- 打出后由会话层发起战斗行动；本实现武装持有者下一次战斗检定
  （同 backstab 的武装约定），加成按打出时你控制卡牌的阵营数计算并锁定。
- "你控制的卡牌"计入场上的支援卡（含中立阵营，中立也是一种阵营）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class GangUp(CardImplementation):
    card_id = "gang_up_lv1"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._armed_for: str | None = None
        self._count = 0

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def arm(self, ctx):
        """打出时：统计你控制卡牌的不同阵营数并武装一次攻击。"""
        if ctx.extra.get("card_id") != self.card_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        classes = set()
        for iid in inv.play_area:
            inst = ctx.game_state.get_card_instance(iid)
            if inst is None:
                continue
            data = ctx.game_state.get_card_data(inst.card_id)
            if data is not None and getattr(data, "card_class", None) is not None:
                classes.add(data.card_class)
        self._armed_for = inv.investigator_id
        self._count = len(classes)
        ctx.extra["gang_up_classes"] = self._count
        if self._count:
            ctx.game_state.log_effect(
                f"🤝 群起而攻：{self._count}种阵营，本次攻击+{self._count}战斗/+{self._count}伤害")

    def _is_this_attack(self, ctx) -> bool:
        return (
            self._armed_for is not None
            and ctx.investigator_id == self._armed_for
            and ctx.skill_type == Skill.COMBAT
            and self._count > 0
        )

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def combat_bonus(self, ctx):
        """每种不同阵营 +1 战斗。"""
        if self._is_this_attack(ctx):
            ctx.modify_amount(self._count, "gang_up_combat_bonus")

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.WHEN)
    def bonus_damage(self, ctx):
        """每种不同阵营 +1 伤害。"""
        if self._is_this_attack(ctx):
            ctx.extra["bonus_damage"] = int(ctx.extra.get("bonus_damage", 0) or 0) + self._count

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        self._armed_for = None
        self._count = 0
