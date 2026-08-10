"""Backstab (Level 0) — Rogue Event.
攻击。本次攻击使用敏捷代替战斗。本次攻击造成+2伤害。

简化说明：
- 打出后由会话层发起战斗行动；本实现通过 active_effects 武装，
  在下一次战斗检定中替换为敏捷值。
- +2伤害通过 SKILL_TEST_SUCCESSFUL 写入 ctx.extra["bonus_damage"]，
  由引擎在攻击成功结算时叠加（与 vicious_blow 同通道）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class Backstab(CardImplementation):
    card_id = "backstab_lv0"

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def arm(self, ctx):
        if ctx.extra.get("card_id") != "backstab_lv0":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if not hasattr(inv, "active_effects"):
            inv.active_effects = {}
        inv.active_effects["backstab_lv0"] = True

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def substitute_agility(self, ctx):
        if ctx.skill_type != Skill.COMBAT:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if not getattr(inv, "active_effects", {}).get("backstab_lv0"):
            return
        base_val = inv.get_skill(ctx.skill_type)
        agility = inv.get_skill(Skill.AGILITY)
        ctx.modify_amount(agility - base_val, "backstab_substitute")

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.AFTER)
    def bonus_damage(self, ctx):
        """本次攻击造成+2伤害（成功时经 bonus_damage 通道结算）。"""
        if ctx.skill_type != Skill.COMBAT:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if not getattr(inv, "active_effects", {}).get("backstab_lv0"):
            return
        ctx.extra["bonus_damage"] = int(ctx.extra.get("bonus_damage", 0) or 0) + 2

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        for inv in ctx.game_state.investigators.values():
            if hasattr(inv, "active_effects"):
                inv.active_effects.pop("backstab_lv0", None)
