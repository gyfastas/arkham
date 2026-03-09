"""Manual Dexterity (Level 0) — Neutral Skill.
心灵手巧。提交到敏捷检定时提供2个敏捷图标。如果检定成功，抽1张牌。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class ManualDexterity(CardImplementation):
    card_id = "manual_dexterity_lv0"

    @on_event(
        GameEvent.SKILL_TEST_SUCCESSFUL,
        priority=TimingPriority.AFTER,
    )
    def draw_on_success(self, ctx):
        """If this skill test is successful, draw 1 card."""
        if "manual_dexterity_lv0" not in ctx.committed_cards:
            return
        if ctx.skill_type != Skill.AGILITY:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv and inv.deck:
            card_id = inv.deck.pop(0)
            inv.hand.append(card_id)
