"""Overpower (Level 0) — Neutral Skill.
压制。提交到战斗检定时提供2个战斗图标。如果检定成功，抽1张牌。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class Overpower(CardImplementation):
    card_id = "overpower_lv0"
    commit_effect_label = "成功后本次攻击额外造成1点伤害"

    @on_event(
        GameEvent.SKILL_TEST_SUCCESSFUL,
        priority=TimingPriority.AFTER,
    )
    def extra_damage(self, ctx):
        """If the optional effect is enabled, add 1 combat damage."""
        if "overpower_lv0" not in ctx.committed_cards:
            return
        if ctx.skill_type != Skill.COMBAT:
            return
        if ctx.extra.get("explicit_effect_selection"):
            ctx.extra["bonus_damage"] = ctx.extra.get("bonus_damage", 0) + 1
            return

        # Preserve the legacy direct-engine behavior used by the existing
        # card test; the interactive UI uses the explicit Chinese effect
        # choice above.
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv and inv.deck:
            inv.hand.append(inv.deck.pop(0))
