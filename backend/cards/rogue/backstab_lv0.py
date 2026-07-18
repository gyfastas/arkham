"""Backstab (Level 0) — Rogue Event.
攻击。本次攻击使用敏捷代替战斗。你获得+2敏捷，本次攻击造成+1伤害。

简化说明：
- 打出后由会话层发起战斗行动；本实现通过 active_effects 武装，
  在下一次战斗检定中替换为敏捷值 +2。
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
        agility = inv.get_skill(Skill.AGILITY)
        ctx.modify_amount(agility - ctx.amount + 2, "backstab_substitute")

    @on_event(GameEvent.DAMAGE_DEALT, priority=TimingPriority.WHEN)
    def bonus_damage(self, ctx):
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if not getattr(inv, "active_effects", {}).get("backstab_lv0"):
            return
        ctx.modify_amount(1, "backstab_bonus_damage")

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        for inv in ctx.game_state.investigators.values():
            if hasattr(inv, "active_effects"):
                inv.active_effects.pop("backstab_lv0", None)
