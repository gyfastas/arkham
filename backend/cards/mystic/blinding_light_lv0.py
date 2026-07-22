"""Blinding Light (Level 0) — Mystic Event.
法术。躲避。本次躲避使用意志代替敏捷。你获得+3敏捷。
如果你成功且超过难度2点以上，返回眩光一闪到你的手中。

简化说明：
- 打出后由会话层发起躲避行动；本实现通过 active_effects 武装，
  在下一次敏捷（躲避）检定中替换为意志值 +3。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class BlindingLight(CardImplementation):
    card_id = "blinding_light_lv0"
    bonus = 3
    return_on_margin = 2

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def arm(self, ctx):
        if ctx.extra.get("card_id") != self.card_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if not hasattr(inv, "active_effects"):
            inv.active_effects = {}
        inv.active_effects[self.card_id] = True

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def substitute_willpower(self, ctx):
        """躲避检定：用意志代替敏捷，并获得加值。"""
        if ctx.skill_type != Skill.AGILITY:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if not getattr(inv, "active_effects", {}).get(self.card_id):
            return
        base_val = inv.get_skill(ctx.skill_type)
        willpower = inv.get_skill(Skill.WILLPOWER)
        ctx.modify_amount(willpower - base_val + self.bonus, f"{self.card_id}_substitute")

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.AFTER)
    def return_to_hand(self, ctx):
        """成功超过难度2点以上：返回手牌。"""
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if not getattr(inv, "active_effects", {}).get(self.card_id):
            return
        if (ctx.modified_skill or 0) - (ctx.difficulty or 0) >= self.return_on_margin:
            if self.card_id in inv.discard:
                inv.discard.remove(self.card_id)
                inv.hand.append(self.card_id)
                ctx.extra[f"{self.card_id}_returned"] = True

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        for inv in ctx.game_state.investigators.values():
            if hasattr(inv, "active_effects"):
                inv.active_effects.pop(self.card_id, None)
