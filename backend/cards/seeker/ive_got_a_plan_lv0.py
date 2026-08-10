"""I've Got a Plan (Level 0) — Seeker Event.
攻击。本次攻击使用智力代替战斗。你每持有1条线索，本次攻击造成+1伤害（最多+3）。

简化说明：
- 打出后由会话层发起战斗行动（与 Backstab 同模式）：本实现通过
  active_effects 武装，在下一次战斗检定中将基础技能值替换为智力；
- 伤害加成在 DAMAGE_DEALT（仅对敌人触发）时按当前持有线索数结算；
- 武装状态在下一次技能检定结束时清除（无论是否用于攻击）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority

_FLAG = "ive_got_a_plan_lv0"


class IveGotAPlan(CardImplementation):
    card_id = "ive_got_a_plan_lv0"

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def arm(self, ctx):
        if ctx.extra.get("card_id") != "ive_got_a_plan_lv0":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if not hasattr(inv, "active_effects"):
            inv.active_effects = {}
        inv.active_effects[_FLAG] = True

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def use_intellect_for_fight(self, ctx):
        """本次攻击用智力代替战斗（图标/标记修正照常生效）。"""
        if ctx.skill_type != Skill.COMBAT:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if not getattr(inv, "active_effects", {}).get(_FLAG):
            return
        base_val = inv.get_skill(ctx.skill_type)
        intellect = inv.get_skill(Skill.INTELLECT)
        diff = intellect - base_val
        if diff != 0:
            ctx.modify_amount(diff, "ive_got_a_plan_substitute")

    @on_event(GameEvent.DAMAGE_DEALT, priority=TimingPriority.WHEN)
    def bonus_damage_from_clues(self, ctx):
        """每持有1条线索+1伤害（最多+3）。"""
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if not getattr(inv, "active_effects", {}).get(_FLAG):
            return
        bonus = min(inv.clues, 3)
        if bonus > 0:
            ctx.modify_amount(bonus, "ive_got_a_plan_bonus_damage")
            ctx.extra["ive_got_a_plan_bonus_damage"] = bonus

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        for inv in ctx.game_state.investigators.values():
            if hasattr(inv, "active_effects"):
                inv.active_effects.pop(_FLAG, None)
