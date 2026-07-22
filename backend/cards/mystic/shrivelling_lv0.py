"""Shrivelling (Level 0) — Mystic Asset, Arcane slot.
使用(4充能)。消耗皱缩术并花费1充能：攻击。本次攻击使用意志代替战斗。
你获得+1战斗，本次攻击造成+1伤害。如果这次攻击揭示一个负面混沌标记，受到1点恐惧。

简化说明：
- activate() 花费1充能并武装；随后由会话层发起战斗行动（weapon_instance_id
  传本卡实例），检定时替换战斗为意志 +1。
- "负面混沌标记"按骷髅/异教徒/石板/古老存在/自动失败处理。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import (
    CHAOS_TOKEN_VALUES, ChaosTokenType, GameEvent, Skill, TimingPriority,
)

_BAD_TOKENS = {
    ChaosTokenType.SKULL, ChaosTokenType.CULTIST,
    ChaosTokenType.TABLET, ChaosTokenType.ELDER_THING,
    ChaosTokenType.AUTO_FAIL,
}


class Shrivelling(CardImplementation):
    card_id = "shrivelling_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._armed = False

    def activate(self, game_state, investigator_id: str) -> bool:
        """花费1充能：武装一次"用意志攻击"。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return False
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None or inst.uses.get("charges", 0) <= 0:
            return False
        inst.uses["charges"] -= 1
        inst.exhausted = True
        self._armed = True
        return True

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def substitute_willpower(self, ctx):
        if not self._armed or ctx.skill_type != Skill.COMBAT:
            return
        if ctx.extra.get("weapon_instance_id") not in (None, self.instance_id):
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        base_val = inv.get_skill(ctx.skill_type)
        willpower = inv.get_skill(Skill.WILLPOWER)
        ctx.modify_amount(willpower - base_val + 1, "shrivelling_substitute")

    @on_event(GameEvent.DAMAGE_DEALT, priority=TimingPriority.WHEN)
    def bonus_damage(self, ctx):
        if not self._armed:
            return
        ctx.modify_amount(1, "shrivelling_bonus_damage")

    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.AFTER)
    def horror_on_bad_token(self, ctx):
        if not self._armed or ctx.chaos_token not in _BAD_TOKENS:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is not None:
            inv.horror += 1
            ctx.extra["shrivelling_horror"] = True

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        self._armed = False
