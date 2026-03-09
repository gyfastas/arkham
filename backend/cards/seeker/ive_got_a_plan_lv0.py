"""I've Got a Plan (Level 0) — Seeker Event.
用智力代替战斗进行攻击。每拥有1条线索+1伤害（最多+3）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class IveGotAPlan(CardImplementation):
    card_id = "ive_got_a_plan_lv0"

    @on_event(
        GameEvent.SKILL_VALUE_DETERMINED,
        priority=TimingPriority.WHEN,
    )
    def use_intellect_for_fight(self, ctx):
        """Use intellect instead of combat for this fight test.

        Skeleton — needs to check that this card is the source of
        the fight action and substitute the skill value.
        """
        if ctx.source != self.instance_id:
            return
        # TODO: replace combat value with intellect value
        pass

    @on_event(
        GameEvent.DAMAGE_DEALT,
        priority=TimingPriority.WHEN,
    )
    def bonus_damage_from_clues(self, ctx):
        """Add extra damage equal to clues held (max +3).

        Skeleton — needs to verify this damage event comes from
        the fight action initiated by this card.
        """
        if ctx.source != self.instance_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        bonus = min(inv.clues, 3)
        if bonus > 0:
            ctx.modify_amount(bonus, "ive_got_a_plan_bonus_damage")
