"""Perception (Level 0) — Neutral Skill.
洞察力。提交到智力检定时提供2个智力图标。如果检定成功，抽1张牌。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class Perception(CardImplementation):
    card_id = "perception_lv0"

    @on_event(
        GameEvent.SKILL_TEST_SUCCESSFUL,
        priority=TimingPriority.AFTER,
    )
    def draw_on_success(self, ctx):
        """If this skill test is successful, draw 1 card."""
        if "perception_lv0" not in ctx.committed_cards:
            return
        if ctx.skill_type != Skill.INTELLECT:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv and inv.deck:
            card_id = inv.deck.pop(0)
            inv.hand.append(card_id)
