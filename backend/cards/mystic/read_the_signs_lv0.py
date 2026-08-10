"""Read the Signs (Level 0) — Mystic Event. (INTC)
调查。本次调查将你的[willpower]值加入技能值。你可以忽略本次调查中将触发的
地点效果或关键词。如果成功，额外发现所在地点1个线索。

简化说明：
- 打出后由会话层发起调查行动；本实现通过 active_effects 武装，
  在下一次智力（调查）检定时加入意志值（同 blinding_light 惯例）。
- "忽略地点效果/关键词"：引擎无地点触发框架（引擎缺口），此处仅声明不生效。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class ReadTheSigns(CardImplementation):
    card_id = "read_the_signs_lv0"

    def _is_armed(self, game_state, investigator_id) -> bool:
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return False
        return bool(getattr(inv, "active_effects", {}).get(self.card_id))

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
    def add_willpower(self, ctx):
        """调查检定：技能值加入意志值。"""
        if ctx.skill_type != Skill.INTELLECT:
            return
        if not self._is_armed(ctx.game_state, ctx.investigator_id):
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        ctx.modify_amount(
            inv.get_skill(Skill.WILLPOWER), f"{self.card_id}_add_willpower")

    @on_event(GameEvent.CLUE_DISCOVERED, priority=TimingPriority.AFTER)
    def bonus_clue(self, ctx):
        """成功：额外发现1个线索。"""
        if not self._is_armed(ctx.game_state, ctx.investigator_id):
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        loc = ctx.game_state.get_location(ctx.location_id or inv.location_id)
        if loc is not None and loc.clues > 0:
            loc.clues -= 1
            inv.clues += 1
            ctx.extra[f"{self.card_id}_extra_clue"] = True

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        for inv in ctx.game_state.investigators.values():
            if getattr(inv, "active_effects", {}).pop(self.card_id, None):
                pass
