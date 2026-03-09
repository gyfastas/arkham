"""Mind over Matter (Level 0) — Seeker Event, Fast.
快速事件：本轮内，战斗和敏捷检定改用智力。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class MindOverMatter(CardImplementation):
    card_id = "mind_over_matter_lv0"

    @on_event(
        GameEvent.CARD_PLAYED,
        priority=TimingPriority.WHEN,
    )
    def activate_effect(self, ctx):
        """When played, mark that Mind over Matter is active for this investigator."""
        if ctx.extra.get("card_id") != "mind_over_matter_lv0":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        # Store active effect on investigator state
        if not hasattr(inv, "active_effects"):
            inv.active_effects = {}
        inv.active_effects["mind_over_matter"] = True

    @on_event(
        GameEvent.SKILL_VALUE_DETERMINED,
        priority=TimingPriority.WHEN,
    )
    def substitute_intellect(self, ctx):
        """If combat or agility test and Mind over Matter active, use intellect."""
        if ctx.skill_type not in (Skill.COMBAT, Skill.AGILITY):
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        active = getattr(inv, "active_effects", {})
        if not active.get("mind_over_matter"):
            return
        # Replace the skill value with intellect
        intellect_val = getattr(inv, "intellect", 0)
        original_val = ctx.amount
        diff = intellect_val - original_val
        if diff != 0:
            ctx.modify_amount(diff, "mind_over_matter_substitution")

    @on_event(
        GameEvent.ROUND_ENDS,
        priority=TimingPriority.AFTER,
    )
    def expire_effect(self, ctx):
        """At end of round, remove Mind over Matter effect."""
        # Clean up all investigators (the event card is already discarded)
        for inv_id in ctx.game_state.investigator_ids:
            inv = ctx.game_state.get_investigator(inv_id)
            if inv and hasattr(inv, "active_effects"):
                inv.active_effects.pop("mind_over_matter", None)
