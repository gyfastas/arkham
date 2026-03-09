"""Encyclopedia (Level 2) — Seeker Asset, Hand slot.
消耗：选择一名在你所在地点的调查员，选择一项技能，该调查员该技能+2直到阶段结束。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class Encyclopedia(CardImplementation):
    card_id = "encyclopedia_lv2"

    def activate(self, ctx, target_id: str | None = None, skill: Skill | None = None):
        """Exhaust: target investigator gets +2 to chosen skill until end of phase.

        Skeleton — stores the buff on the investigator for the skill value
        determination handler to pick up.
        """
        target_id = target_id or ctx.investigator_id
        inv = ctx.game_state.get_investigator(target_id)
        if inv is None or skill is None:
            return
        # Store the active buff
        if not hasattr(inv, "active_effects"):
            inv.active_effects = {}
        inv.active_effects["encyclopedia"] = {
            "skill": skill,
            "amount": 2,
            "source": self.instance_id,
        }

    @on_event(
        GameEvent.SKILL_VALUE_DETERMINED,
        priority=TimingPriority.WHEN,
    )
    def apply_skill_boost(self, ctx):
        """Apply +2 skill bonus if Encyclopedia buff is active for this skill."""
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        buff = getattr(inv, "active_effects", {}).get("encyclopedia")
        if buff is None:
            return
        if buff["source"] != self.instance_id:
            return
        if buff["skill"] == ctx.skill_type:
            ctx.modify_amount(buff["amount"], "encyclopedia_boost")

    @on_event(
        GameEvent.INVESTIGATION_PHASE_ENDS,
        priority=TimingPriority.AFTER,
    )
    def expire_buff(self, ctx):
        """Remove Encyclopedia buff at end of phase."""
        for inv_id in ctx.game_state.investigator_ids:
            inv = ctx.game_state.get_investigator(inv_id)
            if inv is None:
                continue
            buff = getattr(inv, "active_effects", {}).get("encyclopedia")
            if buff and buff["source"] == self.instance_id:
                inv.active_effects.pop("encyclopedia", None)
